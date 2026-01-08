# cclms/api/btm_agent.py

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from redis.exceptions import LockNotOwnedError
import frappe
import requests

PLACES_TEXT_SEARCH_NEW = "https://places.googleapis.com/v1/places:searchText"
GEMINI_GENERATE_TMPL = "https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"

LOCK_KEY = "btm_opportunity_agent_lock"
CACHE_CURSOR_KEY = "btm_agent_last_zip_cursor"


# ----------------------------
# Helpers
# ----------------------------
def _z5(z) -> str:
    return str(z or "").zfill(5)

def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)

def _has_field(doctype: str, fieldname: str) -> bool:
    meta = frappe.get_meta(doctype)
    return any(f.fieldname == fieldname for f in meta.fields)

def _get_places_key() -> str:
    key = frappe.db.get_single_value("Google Maps Settings", "api_key")
    if not key:
        key = frappe.conf.get("maps_api_key") or frappe.conf.get("maps_key")
    if not key:
        frappe.throw("Missing Google Places key. Set Google Maps Settings → api_key.")
    return key

def _get_gemini_key() -> str:
    key = frappe.conf.get("gemini_api_key")
    if not key:
        frappe.throw("Missing gemini_api_key in site config.")
    return key

def _get_gemini_model() -> str:
    return frappe.conf.get("gemini_model") or "gemini-2.5-flash"

def _get_business_types() -> List[str]:
    # business_type is Link -> Business Types, so use DocType "name"
    rows = frappe.get_all("Business Types", fields=["name"], order_by="name asc", limit_page_length=0)
    out = [(r.get("name") or "").strip() for r in rows]
    out = [x for x in out if x]
    if not out:
        frappe.throw("Business Types is empty.")
    return out


# ----------------------------
# Cursor + ZIP batch (ONLY Green/Light Green)
# ----------------------------
def _get_cursor(cfg) -> str:
    if _has_field("ATM Criteria", "last_zip_cursor_btm"):
        return _z5(cfg.get("last_zip_cursor_btm") or "00000")
    return _z5(frappe.cache().get_value(CACHE_CURSOR_KEY) or "00000")

def _set_cursor(cfg, new_cursor: str):
    new_cursor = _z5(new_cursor)
    if _has_field("ATM Criteria", "last_zip_cursor_btm"):
        cfg.db_set("last_zip_cursor_btm", new_cursor)
    else:
        frappe.cache().set_value(CACHE_CURSOR_KEY, new_cursor)

def _get_next_green_zip_batch(cursor_zip: str, batch_size: int) -> List[Dict[str, Any]]:
    cursor_zip = _z5(cursor_zip)

    common_fields = [
        "name", "zip_code", "latitude", "longitude", "city", "state_code",
        "population", "population_density", "zip_score",
        "company_kiosks", "competitor_kiosks", "total_kiosks",
        "kiosks_installed", "kiosks_removed", "kiosks_pending_removal",
        "zone_color",
    ]

    rows = frappe.get_all(
        "Zip Code Analytics",
        fields=common_fields,
        filters={
            "zip_code": [">", cursor_zip],
            "zone_color": ["in", ["Green", "Light Green"]],
            "latitude": ["is", "set"],
            "longitude": ["is", "set"],
        },
        order_by="zip_code asc",
        limit_page_length=int(batch_size),
    )

    # wrap-around
    if not rows:
        rows = frappe.get_all(
            "Zip Code Analytics",
            fields=common_fields,
            filters={
                "zone_color": ["in", ["Green", "Light Green"]],
                "latitude": ["is", "set"],
                "longitude": ["is", "set"],
            },
            order_by="zip_code asc",
            limit_page_length=int(batch_size),
        )

    for r in rows:
        r["zip_code"] = _z5(r.get("zip_code"))
    return rows


# ----------------------------
# Google Places (New) searchText
# IMPORTANT: correct casing -> locationRestriction (camelCase)
# ----------------------------
def _places_text_search(
    api_key: str,
    query: str,
    lat: float,
    lng: float,
    radius_m: int,
    max_results: int,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,"
            "places.displayName,"
            "places.formattedAddress,"
            "places.location,"
            "places.types,"
            "places.nationalPhoneNumber,"
            "places.websiteUri,"
            "places.rating,"
            "places.userRatingCount,"
            "places.addressComponents"
        ),
        "Content-Type": "application/json",
    }

    body: Dict[str, Any] = {
        "textQuery": query,
        "maxResultCount": int(max_results),

        # ✅ use locationBias for circles
        "locationBias": {
            "circle": {
                "center": {"latitude": float(lat), "longitude": float(lng)},
                "radius": int(radius_m),
            }
        },

        # optional but usually helpful
        "rankPreference": "DISTANCE",
        }


    r = requests.post(PLACES_TEXT_SEARCH_NEW, headers=headers, json=body, timeout=25)

    if r.status_code >= 400:
        # log full error
        frappe.log_error(r.text[:5000], f"Places searchText error ({r.status_code}) query={query}")
        return []

    data = r.json() or {}
    places = data.get("places") or []
    if debug:
        frappe.log_error(json.dumps(data)[:5000], f"Places debug query={query}")
    return places


def _extract_components(place: Dict[str, Any]) -> Tuple[str, str, str]:
    zip_code, city, state = "", "", ""
    for c in (place.get("addressComponents") or []):
        types = c.get("types") or []
        text = (c.get("shortText") or c.get("longText") or "").strip()
        if "postal_code" in types and not zip_code:
            zip_code = text
        if ("locality" in types or "postal_town" in types) and not city:
            city = text
        if "administrative_area_level_1" in types and not state:
            state = text
    return zip_code, city, state


# ----------------------------
# Gemini scoring
# ----------------------------
def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def _gemini_score(payload: Dict[str, Any]) -> Dict[str, Any]:
    key = _get_gemini_key()
    model = _get_gemini_model()
    url = GEMINI_GENERATE_TMPL.format(model=model)

    prompt = f"""Return ONLY valid JSON with keys:
{{
  "score": <number 1-100>,
  "pitch": "<one sentence pitch>",
  "reasoning": "<one short paragraph>"
}}

Business:
- name: {payload.get("business_name")}
- address: {payload.get("address")}
- types: {payload.get("types")}

Zip Intelligence:
- zip: {payload.get("zip_code")}
- zone: {payload.get("zone_color")}
- population: {payload.get("population")}
- population_density: {payload.get("population_density")}
- total_kiosks: {payload.get("total_kiosks")}
- competitor_kiosks: {payload.get("competitor_kiosks")}
- company_kiosks: {payload.get("company_kiosks")}
- zip_score: {payload.get("zip_score")}
""".strip()

    req = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 350},
    }

    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=req, timeout=(10,40))


    if r.status_code >= 400:
        frappe.log_error(r.text[:5000], f"Gemini generateContent error ({r.status_code})")
        return {"score": 0, "pitch": "", "reasoning": f"Gemini call failed {r.status_code}", "raw": r.text[:2000]}

    data = r.json() or {}
    text = ""
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass

    js = _extract_json(text) or {}
    return {
        "score": float(js.get("score") or 0),
        "pitch": (js.get("pitch") or "").strip(),
        "reasoning": (js.get("reasoning") or "").strip(),
        "raw": text,
        "model": model,
    }

# ----------------------------
# Insert BTM Opportunity
# ----------------------------
def _duplicate_address(address: str, zip_code: str) -> Optional[str]:
    if not address or not zip_code:
        return None
    return frappe.db.get_value("BTM Opportunity", {"address": address, "zip_code": zip_code}, "name")

def _create_btm_opportunity(place: Dict[str, Any], zip_row: Dict[str, Any], business_type_name: str, ai: Dict[str, Any]) -> bool:
    place_id = place.get("id")
    if not place_id:
        return False

    if frappe.db.exists("BTM Opportunity", {"place_id": place_id}):
        return False

    name = ((place.get("displayName") or {}).get("text") or "").strip()
    address = (place.get("formattedAddress") or "").strip()

    loc = place.get("location") or {}
    lat = loc.get("latitude")
    lng = loc.get("longitude")

    place_zip, city, state = _extract_components(place)
    zip_code = _z5(zip_row.get("zip_code") or place_zip)

    dup_of = _duplicate_address(address, zip_code)

    doc = frappe.new_doc("BTM Opportunity")
    doc.place_id = place_id
    doc.business_name = name or "Unknown"
    doc.business_type = business_type_name
    doc.address = address
    doc.city = city or (zip_row.get("city") or "")
    doc.state_code = state or (zip_row.get("state_code") or "")
    doc.zip_code = zip_code
    doc.latitude = float(lat) if lat is not None else None
    doc.longitude = float(lng) if lng is not None else None

    doc.phone = (place.get("nationalPhoneNumber") or "")[:140]
    doc.website = str(place.get("websiteUri") or "")[:300]
    doc.google_rating = _num(place.get("rating"), 0)
    doc.user_ratings_total = int(place.get("userRatingCount") or 0)

    doc.source = "gemini_agent"
    doc.ai_score = float(ai.get("score") or 0)
    doc.ai_pitch = ai.get("pitch") or ""
    doc.ai_reasoning = ai.get("reasoning") or ""

    safe_pitch = frappe.utils.escape_html(doc.ai_pitch)
    safe_reason = frappe.utils.escape_html(doc.ai_reasoning)
    doc.ai_analysis_html = (
        f"<div style='padding:10px;border-left:4px solid #2563eb;background:#eff6ff;border-radius:6px'>"
        f"<b>AI Score:</b> {doc.ai_score}<br>"
        f"<b>Pitch:</b> {safe_pitch}<br>"
        f"<b>Reason:</b> {safe_reason}</div>"
    )

    if dup_of:
        doc.duplicate_check = 1
        doc.duplicate_of = dup_of  # ensure field options is "BTM Opportunity"
        doc.status = "Rejected"
    else:
        doc.status = "New"

    doc.insert(ignore_permissions=True)
    return True


# ----------------------------
# Public run
# ----------------------------
@frappe.whitelist()
def run_btm_batch(limit_zips: int = 2) -> Dict[str, Any]:
    cfg = frappe.get_single("ATM Criteria")
    if not int(cfg.get("enabled") or 0):
        return {"ok": False, "msg": "ATM Criteria disabled"}

    # Make lock timeout long enough for batch runs
    lock = frappe.cache().lock(LOCK_KEY, timeout=7200)  # 2 hours

    if not lock.acquire(blocking=False):
        return {"ok": False, "msg": "BTM agent already running"}

    try:
        places_key = _get_places_key()
        business_types = _get_business_types()

        min_ai_score = float(cfg.get("min_ai_score") or 80)
        radius_m = int(cfg.get("places_radius_m") or 12000)
        max_results = int(cfg.get("max_places_per_type") or 15)

        cursor = _get_cursor(cfg)
        zip_batch = _get_next_green_zip_batch(cursor, int(limit_zips))

        created = 0
        scanned = 0

        for zr in zip_batch:
            lat = float(zr["latitude"])
            lng = float(zr["longitude"])
            zip_code = zr["zip_code"]

            for bt in business_types:
                query = f"{bt} near {zip_code}"

                places = _places_text_search(
                    places_key,
                    query,
                    lat,
                    lng,
                    radius_m,
                    max_results,
                )

                for p in places:
                    scanned += 1

                    payload = {
                        "business_name": ((p.get("displayName") or {}).get("text") or ""),
                        "address": (p.get("formattedAddress") or ""),
                        "types": p.get("types") or [],
                        "zip_code": zip_code,
                        "zone_color": zr.get("zone_color"),
                        "population": zr.get("population"),
                        "population_density": zr.get("population_density"),
                        "total_kiosks": zr.get("total_kiosks"),
                        "competitor_kiosks": zr.get("competitor_kiosks"),
                        "company_kiosks": zr.get("company_kiosks"),
                        "zip_score": zr.get("zip_score"),
                    }

                    ai = _gemini_score(payload)
                    if (ai.get("score") or 0) < min_ai_score:
                        continue

                    if _create_btm_opportunity(p, zr, bt, ai):
                        created += 1

                    time.sleep(0.2)

        # move cursor forward
        if zip_batch:
            _set_cursor(cfg, zip_batch[-1]["zip_code"])

        frappe.db.commit()
        return {
            "ok": True,
            "cursor_from": cursor,
            "cursor_to": (zip_batch[-1]["zip_code"] if zip_batch else cursor),
            "zip_rows_loaded": len(zip_batch),
            "places_scanned": scanned,
            "opportunities_created": created,
        }

    finally:
        # ✅ SAFE LOCK RELEASE (prevents LockNotOwnedError after Ctrl+C / timeout)
        try:
            if lock and lock.owned():
                lock.release()
        except Exception:
            # ignore lock release errors
            pass

def run_btm_minutely():
    try:
        run_btm_batch(limit_zips=2)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "BTM Opportunity agent failed")
