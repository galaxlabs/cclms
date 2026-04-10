import csv
import json
import os
from typing import Dict, List, Optional

import frappe
import requests
from frappe.utils import flt, now_datetime


SCOUTING_CSV_PATH = (
    "/home/dg/dg-b/sites/crm.galaxylabs.online/private/files/"
    "Zip Codes Scouting Report - 10.06.csv"
)
GOOGLE_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)


def _z5(value) -> str:
    value = str(value or "").strip()
    return value.zfill(5) if value.isdigit() else value


def _as_float(value, default=None):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _as_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def _normalize_score(value, floor=0, ceiling=100):
    return max(floor, min(ceiling, flt(value)))


def _strip_json_fences(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1] if "\n" in value else value
        if value.endswith("```"):
            value = value[:-3]
    return value.strip()


def _compute_scores(zip_row):
    zip_score = flt((zip_row or {}).get("zip_score"))
    density = flt((zip_row or {}).get("population_density"))
    competitor = flt((zip_row or {}).get("competitor_density") or (zip_row or {}).get("competitor_kiosks"))
    removal_rate = flt((zip_row or {}).get("removal_rate"))
    saturation_rate = flt((zip_row or {}).get("saturation_rate"))

    competitor_density_score = _normalize_score(100 - (competitor * 10))
    risk_score = _normalize_score((removal_rate * 100) + saturation_rate + (25 if (zip_row or {}).get("zone_color") == "Red" else 0))
    operator_fit_score = _normalize_score((zip_score * 0.6) + (density / 100) + competitor_density_score * 0.2 - risk_score * 0.2)
    return competitor_density_score, risk_score, operator_fit_score


def _mile_distance(lat1, lng1, lat2, lng2) -> Optional[float]:
    lat1 = _as_float(lat1)
    lng1 = _as_float(lng1)
    lat2 = _as_float(lat2)
    lng2 = _as_float(lng2)
    if None in (lat1, lng1, lat2, lng2):
        return None

    from math import atan2, cos, radians, sin, sqrt

    radius_miles = 3958.7613
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * radius_miles * atan2(sqrt(a), sqrt(1 - a))


def _zip_row(zip_code: str):
    zip_code = _z5(zip_code)
    if not zip_code:
        return None
    return frappe.db.get_value("Zip Code Analytics", {"zip_code": zip_code}, "*", as_dict=True)


def _next_zip_batch(limit: int = 20) -> List[str]:
    cache = frappe.cache()
    cursor = _z5(cache.get_value("cclms_zipintel_intelligence_cursor") or "00000")

    rows = frappe.get_all(
        "Zip Code Analytics",
        fields=["zip_code"],
        filters={"zip_code": [">", cursor]},
        order_by="zip_code asc",
        limit_page_length=int(limit),
    )
    if not rows:
        rows = frappe.get_all(
            "Zip Code Analytics",
            fields=["zip_code"],
            order_by="zip_code asc",
            limit_page_length=int(limit),
        )

    zip_codes = [_z5(row.get("zip_code")) for row in rows if row.get("zip_code")]
    if zip_codes:
        cache.set_value("cclms_zipintel_intelligence_cursor", zip_codes[-1])
    return zip_codes


def _competitor_rows_for_zip(zip_code: str, limit: int = 200) -> List[Dict]:
    zip_code = _z5(zip_code)
    if not zip_code:
        return []

    return frappe.db.sql(
        """
        SELECT
            name, brand, display_name, address, city, state_code,
            zip_code, actual_zip_code, latitude, longitude, source, provider, last_seen_on
        FROM `tabCompetitor Kiosk`
        WHERE COALESCE(NULLIF(actual_zip_code, ''), NULLIF(zip_code, '')) = %(zip_code)s
        ORDER BY IFNULL(last_seen_on, modified) DESC
        LIMIT %(limit)s
        """,
        {"zip_code": zip_code, "limit": int(limit)},
        as_dict=True,
    )


def _lead_rows_for_zip(zip_code: str, exclude_name: Optional[str] = None, limit: int = 200) -> List[Dict]:
    zip_code = _z5(zip_code)
    if not zip_code:
        return []

    filters = ["zip_code = %(zip_code)s", "latitude IS NOT NULL", "longitude IS NOT NULL"]
    params = {"zip_code": zip_code, "limit": int(limit)}
    if exclude_name:
        filters.append("name != %(exclude_name)s")
        params["exclude_name"] = exclude_name

    return frappe.db.sql(
        f"""
        SELECT
            name, business_name, workflow_state, latitude, longitude, address, city, state
        FROM `tabATM Leads`
        WHERE {" AND ".join(filters)}
        ORDER BY modified DESC
        LIMIT %(limit)s
        """,
        params,
        as_dict=True,
    )


def _nearest_distance(origin_lat, origin_lng, rows: List[Dict]) -> Optional[float]:
    distances = []
    for row in rows:
        distance = _mile_distance(origin_lat, origin_lng, row.get("latitude"), row.get("longitude"))
        if distance is not None:
            distances.append(distance)
    return min(distances) if distances else None


def _population_updates_from_csv(limit: int = 20, only_missing: bool = True, zip_codes: Optional[List[str]] = None) -> Dict:
    if not os.path.exists(SCOUTING_CSV_PATH):
        return {"processed": 0, "updated": 0, "skipped": 0, "reason": "csv_missing"}

    zip_filter = {_z5(z) for z in (zip_codes or []) if _z5(z)}
    updated = 0
    skipped = 0
    processed = 0

    with open(SCOUTING_CSV_PATH, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            zip_code = _z5(row.get("zip_code"))
            if not zip_code:
                continue
            if zip_filter and zip_code not in zip_filter:
                continue

            target = frappe.db.get_value("Zip Code Analytics", {"zip_code": zip_code}, "*", as_dict=True)
            if not target:
                skipped += 1
                continue

            processed += 1
            values = {
                "city": (row.get("City") or "").strip(),
                "state_code": (row.get("State") or "").strip(),
                "location_flag": (row.get("Location Analytics Flag") or "").strip(),
                "population": _as_int(row.get("Blended Pop Estimate")),
                "population_density": _as_float(row.get("Pop Density"), 0),
                "square_miles": _as_float(row.get("Square Miles"), 0),
                "land_sq_mi": _as_float(row.get("Land_SQMI_from_gaz"), 0),
                "water_sq_mi": _as_float(row.get("Water_SQMI_from_gaz"), 0),
                "latitude": _as_float(row.get("Latitude_from_gaz")),
                "longitude": _as_float(row.get("Longitude_from_gaz")),
                "geo_id_fq": (row.get("geo_id_fq") or "").strip(),
            }

            changes = {}
            for fieldname, value in values.items():
                existing = target.get(fieldname)
                if only_missing:
                    if existing in (None, "", 0, 0.0) and value not in (None, "", 0, 0.0):
                        changes[fieldname] = value
                elif value not in (None, "") and existing != value:
                    changes[fieldname] = value

            if changes:
                frappe.db.set_value("Zip Code Analytics", target.name, changes, update_modified=False)
                updated += 1
            else:
                skipped += 1

            if processed >= int(limit):
                break

    return {"processed": processed, "updated": updated, "skipped": skipped}


def refresh_zip_competitor_cache(zip_codes: Optional[List[str]] = None, limit: int = 20) -> Dict:
    if zip_codes:
        zip_list = [_z5(z) for z in zip_codes if _z5(z)]
    else:
        zip_list = _next_zip_batch(limit=limit)

    if not zip_list:
        return {"processed": 0, "updated": 0}

    counts = frappe.db.sql(
        """
        SELECT COALESCE(NULLIF(actual_zip_code, ''), NULLIF(zip_code, '')) AS zip_code, COUNT(*) AS cnt
        FROM `tabCompetitor Kiosk`
        WHERE COALESCE(NULLIF(actual_zip_code, ''), NULLIF(zip_code, '')) IN %(zip_list)s
        GROUP BY COALESCE(NULLIF(actual_zip_code, ''), NULLIF(zip_code, ''))
        """,
        {"zip_list": tuple(zip_list)},
        as_dict=True,
    )
    count_map = {_z5(row.zip_code): int(row.cnt or 0) for row in counts}

    lead_counts = frappe.db.sql(
        """
        SELECT zip_code, COUNT(*) AS cnt
        FROM `tabATM Leads`
        WHERE zip_code IN %(zip_list)s
          AND workflow_state IN ('Approved', 'Agreement Sent', 'Pending Sign', 'Signed', 'Converted', 'Install Scheduled', 'Installed')
        GROUP BY zip_code
        """,
        {"zip_list": tuple(zip_list)},
        as_dict=True,
    )
    lead_map = {_z5(row.zip_code): int(row.cnt or 0) for row in lead_counts}

    updated = 0
    now = now_datetime()
    for zip_code in zip_list:
        row = _zip_row(zip_code)
        if not row:
            continue

        competitor_count = count_map.get(zip_code, 0)
        company_count = lead_map.get(zip_code, _as_int(row.get("company_kiosks"), 0))
        total_kiosks = competitor_count + company_count
        land_sq_mi = _as_float(row.get("land_sq_mi")) or _as_float(row.get("square_miles")) or 0
        competitor_density = int(round(competitor_count / land_sq_mi)) if land_sq_mi else competitor_count

        changes = {
            "competitor_kiosks": competitor_count,
            "company_kiosks": company_count,
            "total_kiosks": total_kiosks,
            "competitor_density": competitor_density,
            "last_score_update": now,
        }

        if row.get("latitude") in (None, "", 0, 0.0) or row.get("longitude") in (None, "", 0, 0.0):
            sample_point = frappe.db.sql(
                """
                SELECT latitude, longitude
                FROM `tabCompetitor Kiosk`
                WHERE COALESCE(NULLIF(actual_zip_code, ''), NULLIF(zip_code, '')) = %(zip_code)s
                  AND latitude IS NOT NULL
                  AND longitude IS NOT NULL
                ORDER BY IFNULL(last_seen_on, modified) DESC
                LIMIT 1
                """,
                {"zip_code": zip_code},
                as_dict=True,
            )
            if sample_point:
                changes["latitude"] = sample_point[0].latitude
                changes["longitude"] = sample_point[0].longitude

        frappe.db.set_value("Zip Code Analytics", row.name, changes, update_modified=False)
        updated += 1

    return {"processed": len(zip_list), "updated": updated, "zip_codes": zip_list}


def build_lead_intelligence(lead_or_name, write_zip_centroid: bool = False) -> Dict:
    lead = lead_or_name if getattr(lead_or_name, "doctype", None) == "ATM Leads" else frappe.get_doc("ATM Leads", lead_or_name)

    zip_code = _z5(getattr(lead, "zip_code", None))
    zip_row = _zip_row(zip_code)
    lead_lat = _as_float(getattr(lead, "latitude", None))
    lead_lng = _as_float(getattr(lead, "longitude", None))

    competitor_rows = _competitor_rows_for_zip(zip_code)
    nearby_leads = _lead_rows_for_zip(zip_code, exclude_name=lead.name)

    nearest_competitor_miles = _nearest_distance(lead_lat, lead_lng, competitor_rows)
    nearest_same_zip_lead_miles = _nearest_distance(lead_lat, lead_lng, nearby_leads)

    if write_zip_centroid and zip_row and lead_lat is not None and lead_lng is not None:
        if zip_row.get("latitude") in (None, "", 0, 0.0) or zip_row.get("longitude") in (None, "", 0, 0.0):
            frappe.db.set_value(
                "Zip Code Analytics",
                zip_row.name,
                {"latitude": lead_lat, "longitude": lead_lng},
                update_modified=False,
            )

    zone = (zip_row or {}).get("zone_color") or (zip_row or {}).get("zone") or "Unknown"
    competitor_count = len(competitor_rows)
    zip_competitor_count = _as_int((zip_row or {}).get("competitor_kiosks"), competitor_count)

    distance_threshold = 1.0
    distance_ok = True
    blockers = []
    if nearest_competitor_miles is not None and nearest_competitor_miles <= distance_threshold:
        distance_ok = False
        blockers.append(f"nearest competitor kiosk is only {nearest_competitor_miles:.2f} miles away")
    if nearest_same_zip_lead_miles is not None and nearest_same_zip_lead_miles <= distance_threshold:
        distance_ok = False
        blockers.append(f"nearest existing ATM lead in the same ZIP is {nearest_same_zip_lead_miles:.2f} miles away")
    if zone == "Red":
        blockers.append("ZIP is currently classified as Red")

    qualifies = zone != "Red" and distance_ok
    recommendation = (
        "Qualified for operator submission. Distance clearance is healthy and ZIP quality is acceptable."
        if qualifies
        else "Hold submission and review manually before sending to the operator."
    )
    if blockers:
        recommendation = f"{recommendation} Blockers: " + "; ".join(blockers)

    competitor_density_score, risk_score, operator_fit_score = _compute_scores(zip_row or {})
    suggested_radius_m = 1609 if qualifies else 804

    return {
        "lead": lead.name,
        "zip_code": zip_code,
        "zone_color": zone,
        "zip_score": flt((zip_row or {}).get("zip_score")),
        "matched_rule": (zip_row or {}).get("matched_rule"),
        "competitor_kiosks": zip_competitor_count,
        "competitor_rows_in_truth": competitor_count,
        "nearest_competitor_miles": round(nearest_competitor_miles, 2) if nearest_competitor_miles is not None else None,
        "nearest_same_zip_lead_miles": round(nearest_same_zip_lead_miles, 2) if nearest_same_zip_lead_miles is not None else None,
        "distance_threshold_miles": distance_threshold,
        "distance_ok": distance_ok,
        "qualified_for_approval": qualifies,
        "suggested_search_radius_m": suggested_radius_m,
        "recommended_next_action": recommendation,
        "competitor_density_score": competitor_density_score,
        "risk_score": risk_score,
        "operator_fit_score": operator_fit_score,
    }


def _get_gemini_api_key() -> Optional[str]:
    key = frappe.conf.get("gemini_api_key")
    if key:
        return key

    try:
        if frappe.db.exists("DocType", "AI Policy"):
            policy = frappe.get_single("AI Policy")
            if getattr(policy, "gemini_api_key", None):
                try:
                    secret = policy.get_password("gemini_api_key")
                    if secret:
                        return secret
                except Exception:
                    pass
    except Exception:
        pass

    # Backward-compatible fallback for environments that stored a single Google key.
    return frappe.db.get_single_value("Google Maps Settings", "api_key")


def _get_gemini_model() -> str:
    model = frappe.conf.get("gemini_model")
    if model:
        return model

    try:
        if frappe.db.exists("DocType", "AI Policy"):
            policy = frappe.get_single("AI Policy")
            if getattr(policy, "gemini_model", None):
                return policy.gemini_model
    except Exception:
        pass

    return "gemini-2.5-flash"


def generate_zip_ai_hint(zip_code: str, place_context: Optional[Dict] = None) -> Optional[Dict]:
    zip_row = _zip_row(zip_code)
    if not zip_row:
        return None

    key = _get_gemini_api_key()
    model = _get_gemini_model()
    if not key:
        return {
            "provider": "gemini",
            "zip_code": zip_code,
            "raw_text": "",
            "summary": "",
            "next_action": "",
            "caution": "",
            "foot_traffic_estimate": "",
            "suitability_note": "",
            "available": False,
            "reason": "missing_gemini_key",
        }

    prompt = {
        "zip_code": zip_code,
        "city": zip_row.get("city"),
        "state_code": zip_row.get("state_code"),
        "location_flag": zip_row.get("location_flag"),
        "zip_score": zip_row.get("zip_score"),
        "zone_color": zip_row.get("zone_color"),
        "population": zip_row.get("population"),
        "population_density": zip_row.get("population_density"),
        "competitor_kiosks": zip_row.get("competitor_kiosks"),
        "company_kiosks": zip_row.get("company_kiosks"),
        "matched_rule": zip_row.get("matched_rule"),
    }
    if place_context:
        prompt["place_context"] = {
            "business_name": place_context.get("business_name"),
            "category": place_context.get("category"),
            "address": place_context.get("address"),
            "city": place_context.get("city"),
            "state_code": place_context.get("state_code") or place_context.get("state"),
            "google_rating": place_context.get("google_rating"),
            "user_ratings_total": place_context.get("user_ratings_total"),
            "open_now_text": place_context.get("open_now_text"),
            "website": place_context.get("website"),
            "phone": place_context.get("phone"),
            "distance_metrics": place_context.get("distance_metrics"),
        }

    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "You are Galaxy Smart Tool, a strategic Bitcoin ATM scouting assistant for CCLMS. "
                            "Write a short JSON object with keys summary, next_action, caution, "
                            "foot_traffic_estimate, and suitability_note. "
                            "Use real values from the provided ZIP and place context such as Google rating, "
                            "review count, category, hours, and distance metrics when available. "
                            "Do not invent exact foot traffic or private Google Business Manager data. "
                            "If exact foot traffic is unavailable from current public sources, say that clearly "
                            "and give only a cautious estimate based on public proxies. "
                            "If the ZIP score is good and the location distance metrics are healthy, clearly say "
                            "that this location will have more chance to win. "
                            "If a nearby Bitcoin Depot machine or competitor is too close, explain that the kiosk "
                            "distance metrics are important and should be reviewed. "
                            f"Analyze this ZIP: {frappe.as_json(prompt)}"
                        )
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(
            f"{GOOGLE_GEMINI_ENDPOINT.format(model=model)}?key={key}",
            json=body,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json() or {}
        text = (
            (((payload.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text")
            or ""
        ).strip()
        if not text:
            return None
        parsed = {}
        try:
            parsed = json.loads(_strip_json_fences(text))
        except Exception:
            parsed = {}
        return {
            "provider": "gemini",
            "zip_code": zip_code,
            "model": model,
            "raw_text": text,
            "summary": parsed.get("summary") or "",
            "next_action": parsed.get("next_action") or "",
            "caution": parsed.get("caution") or "",
            "foot_traffic_estimate": parsed.get("foot_traffic_estimate") or "",
            "suitability_note": parsed.get("suitability_note") or "",
            "available": True,
            "reason": "",
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"ZIP Gemini hint failed for {zip_code}")
        return {
            "provider": "gemini",
            "zip_code": zip_code,
            "model": model,
            "raw_text": "",
            "summary": "",
            "next_action": "",
            "caution": "",
            "foot_traffic_estimate": "",
            "suitability_note": "",
            "available": False,
            "reason": "gemini_request_failed",
        }


@frappe.whitelist()
def get_lead_validation_snapshot(lead_name: str) -> Dict:
    return build_lead_intelligence(lead_name, write_zip_centroid=False)


def run_five_minute_intelligence(batch_size: int = 20, ai_limit: int = 3) -> Dict:
    from cclms.api.competitor_agent import run_competitor_batch

    batch_size = max(1, min(int(batch_size or 20), 20))
    zip_codes = _next_zip_batch(limit=batch_size)
    population = _population_updates_from_csv(limit=batch_size, only_missing=True, zip_codes=zip_codes)
    competitor = run_competitor_batch(batch_size=batch_size)
    cache = refresh_zip_competitor_cache(zip_codes=zip_codes, limit=batch_size)

    ai_results = []
    for zip_code in cache.get("zip_codes", [])[: max(0, int(ai_limit or 0))]:
        hint = generate_zip_ai_hint(zip_code)
        if not hint:
            continue
        zip_row = _zip_row(zip_code)
        if zip_row:
            frappe.db.set_value("Zip Code Analytics", zip_row.name, "demo_json", frappe.as_json(hint, indent=2), update_modified=False)
            ai_results.append({"zip_code": zip_code, "provider": hint.get("provider")})

    frappe.db.commit()
    return {
        "ok": True,
        "population": population,
        "competitor": competitor,
        "cache": cache,
        "ai_results": ai_results,
    }
