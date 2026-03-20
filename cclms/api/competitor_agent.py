# cclms/api/competitor_agent.py

import time
from typing import Dict, Any, List, Tuple, Optional

import frappe
import requests
from frappe.utils import now_datetime, add_days

PLACES_TEXT_SEARCH_NEW = "https://places.googleapis.com/v1/places:searchText"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"  # you can add fallback endpoints later


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


def _get_places_key() -> str:
    key = frappe.db.get_single_value("Google Maps Settings", "api_key")
    if not key:
        key = frappe.conf.get("maps_api_key") or frappe.conf.get("maps_key")
    if not key:
        frappe.throw("Missing Google Places key. Set Google Maps Settings → api_key.")
    return key


def _get_operator_companies() -> List[str]:
    """
    Reads from your Desk DocType: Operator Companies
    operator_name is unique.
    """
    try:
        ops = frappe.get_all("Operator Companies", fields=["operator_name"], limit_page_length=0)
        names = [o.get("operator_name") for o in ops if o.get("operator_name")]
        return [str(x).strip() for x in names if str(x).strip()]
    except Exception:
        # If DocType missing or empty, fallback to conf list
        ops = frappe.conf.get("competitor_brands")
        if isinstance(ops, list) and ops:
            return [str(b).strip() for b in ops if str(b).strip()]
        return ["CoinFlip", "Coinhub", "RockItCoin", "Athena", "Bitcoin of America", "Bitcoin Depot"]


def _infer_operator(display_name: str, address: str, operator_names: List[str]) -> str:
    """
    Infer operator from text match.
    If none matches: Unknown
    """
    txt = f"{display_name or ''} {address or ''}".lower()
    for op in operator_names:
        if op.lower() in txt:
            return op
    # common patterns
    if "coinflip" in txt:
        return "CoinFlip"
    if "coin hub" in txt or "coinhub" in txt:
        return "Coinhub"
    if "rockitcoin" in txt or "rock it coin" in txt:
        return "RockItCoin"
    if "bitcoin depot" in txt:
        return "Bitcoin Depot"
    return "Unknown"


def _get_next_zip_batch(cursor_zip: str, batch_size: int) -> List[Dict[str, Any]]:
    """
    Cursor-based scan of Zip Code Analytics.
    Only zips with lat/lng are included.
    Wraps around at end.
    """
    cursor_zip = _z5(cursor_zip or "00000")

    rows = frappe.get_all(
        "Zip Code Analytics",
        fields=["name", "zip_code", "latitude", "longitude", "city", "state_code"],
        filters={
            "zip_code": [">", cursor_zip],
            "latitude": ["is", "set"],
            "longitude": ["is", "set"],
        },
        order_by="zip_code asc",
        limit_page_length=int(batch_size),
    )

    if not rows:
        rows = frappe.get_all(
            "Zip Code Analytics",
            fields=["name", "zip_code", "latitude", "longitude", "city", "state_code"],
            filters={"latitude": ["is", "set"], "longitude": ["is", "set"]},
            order_by="zip_code asc",
            limit_page_length=int(batch_size),
        )

    for r in rows:
        r["zip_code"] = _z5(r.get("zip_code"))
    return rows


# ----------------------------
# Google Places (New)
# ----------------------------
def _places_text_search(
    api_key: str,
    query: str,
    lat: float,
    lng: float,
    radius_m: int,
    max_results: int,
    use_restriction: bool = True,
) -> List[Dict[str, Any]]:
    """
    IMPORTANT:
    - Global search returns {} for you (as you saw).
    - Always include locationBias or locationRestriction.
    """
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,"
            "places.displayName,"
            "places.formattedAddress,"
            "places.location,"
            "places.addressComponents"
        ),
        "Content-Type": "application/json",
    }

    loc = {
        "circle": {
            "center": {"latitude": float(lat), "longitude": float(lng)},
            "radius": int(radius_m),
        }
    }

    body: Dict[str, Any] = {
        "textQuery": query,
        "maxResultCount": int(max_results),
    }

    # restriction is stronger / cleaner than bias
    if use_restriction:
        body["locationRestriction"] = loc
    else:
        body["locationBias"] = loc

    r = requests.post(PLACES_TEXT_SEARCH_NEW, headers=headers, json=body, timeout=25)
    if r.status_code >= 400:
        frappe.log_error(r.text, f"Google Places searchText error ({r.status_code})")
        return []

    data = r.json() or {}
    return data.get("places") or []


def _extract_components(place: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return (zip, city, state_code) from Places addressComponents."""
    zip_code = ""
    city = ""
    state = ""

    comps = place.get("addressComponents") or []
    for c in comps:
        types = c.get("types") or []
        text = (c.get("shortText") or c.get("longText") or "").strip()

        if "postal_code" in types and not zip_code:
            zip_code = text
        if ("locality" in types or "postal_town" in types) and not city:
            city = text
        if "administrative_area_level_1" in types and not state:
            state = text

    return zip_code, city, state


def _search_google_competitor(
    api_key: str,
    operator_names: List[str],
    zc: str,
    lat: float,
    lng: float,
    radius_m: int,
    max_results: int,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Strategy:
    - 1) generic "bitcoin atm near zip"
    - 2) each operator "OP bitcoin atm near zip"
    """
    # Generic first: catches kiosks that don't show the brand in name
    generic_queries = [
        f"bitcoin atm near {zc}",
        f"crypto atm near {zc}",
        f"bitcoin kiosk near {zc}",
    ]
    for q in generic_queries:
        places = _places_text_search(api_key, q, lat, lng, radius_m, max_results, use_restriction=True)
        if places:
            return places, q

    # Brand queries next
    brand_queries = [
        "bitcoin atm near {zip}",
        "crypto atm near {zip}",
        "atm near {zip}",
    ]
    for op in operator_names:
        for fmt in brand_queries:
            q = f"{op} {fmt.format(zip=zc)}"
            places = _places_text_search(api_key, q, lat, lng, radius_m, max_results, use_restriction=True)
            if places:
                return places, q

    return [], None


# ----------------------------
# OSM / Overpass (free)
# ----------------------------
def _overpass_query(lat: float, lng: float, radius_m: int) -> str:
    """
    We try to find bitcoin ATMs and crypto ATMs.
    Common OSM tags:
      amenity=atm + currency:BTC=yes
      amenity=atm + operator=...
      brand=...
      atm=yes + cryptocurrency tags
      payment:bitcoin=yes
    """
    r = int(radius_m)
    # Overpass QL
    return f"""
    [out:json][timeout:25];
    (
      node(around:{r},{lat},{lng})["amenity"="atm"]["currency:BTC"="yes"];
      way(around:{r},{lat},{lng})["amenity"="atm"]["currency:BTC"="yes"];
      relation(around:{r},{lat},{lng})["amenity"="atm"]["currency:BTC"="yes"];

      node(around:{r},{lat},{lng})["amenity"="atm"]["payment:bitcoin"="yes"];
      way(around:{r},{lat},{lng})["amenity"="atm"]["payment:bitcoin"="yes"];
      relation(around:{r},{lat},{lng})["amenity"="atm"]["payment:bitcoin"="yes"];

      node(around:{r},{lat},{lng})["amenity"="atm"]["operator"~"bitcoin|crypto|CoinFlip|Coinhub|RockItCoin|Athena|Depot", i];
      way(around:{r},{lat},{lng})["amenity"="atm"]["operator"~"bitcoin|crypto|CoinFlip|Coinhub|RockItCoin|Athena|Depot", i];
      relation(around:{r},{lat},{lng})["amenity"="atm"]["operator"~"bitcoin|crypto|CoinFlip|Coinhub|RockItCoin|Athena|Depot", i];

      node(around:{r},{lat},{lng})["name"~"bitcoin atm|crypto atm", i];
      way(around:{r},{lat},{lng})["name"~"bitcoin atm|crypto atm", i];
      relation(around:{r},{lat},{lng})["name"~"bitcoin atm|crypto atm", i];
    );
    out center tags;
    """


def _search_osm_bitcoin_atms(lat: float, lng: float, radius_m: int) -> List[Dict[str, Any]]:
    q = _overpass_query(lat, lng, radius_m)
    try:
        r = requests.post(OVERPASS_URL, data=q.encode("utf-8"), timeout=30)
        if r.status_code >= 400:
            frappe.log_error(r.text[:2000], f"Overpass error ({r.status_code})")
            return []
        data = r.json() or {}
        return data.get("elements") or []
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Overpass request failed")
        return []


def _osm_element_to_place(el: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize Overpass element to a "place-like" structure.
    """
    el_type = el.get("type")  # node/way/relation
    el_id = el.get("id")
    tags = el.get("tags") or {}

    name = tags.get("name") or tags.get("brand") or tags.get("operator") or "Bitcoin ATM"
    operator = tags.get("operator") or tags.get("brand") or ""
    addr = tags.get("addr:full") or ""
    city = tags.get("addr:city") or ""
    state = tags.get("addr:state") or tags.get("addr:region") or ""
    postcode = tags.get("addr:postcode") or ""

    if el_type == "node":
        lat = el.get("lat")
        lng = el.get("lon")
    else:
        center = el.get("center") or {}
        lat = center.get("lat")
        lng = center.get("lon")

    return {
        "osm_id": f"{el_type}:{el_id}",
        "display_name": str(name),
        "operator_hint": str(operator),
        "address": str(addr),
        "city": str(city),
        "state_code": str(state),
        "zip_code": str(postcode),
        "latitude": lat,
        "longitude": lng,
        "raw_tags": tags,
    }


# ----------------------------
# Upsert Competitor Kiosk
# ----------------------------
def _upsert_competitor_google(operator_name: str, place: Dict[str, Any], fallback_zip: str) -> bool:
    """
    Upsert by place_id for Google.
    Returns True if created.
    """
    place_id = place.get("id")
    if not place_id:
        return False

    display_name = ((place.get("displayName") or {}).get("text") or "").strip()
    address = (place.get("formattedAddress") or "").strip()
    loc = place.get("location") or {}
    lat = loc.get("latitude")
    lng = loc.get("longitude")
    place_zip, city, state = _extract_components(place)
    zip_code = _z5(place_zip or fallback_zip)

    now = now_datetime()

    existing_name = frappe.db.get_value("Competitor Kiosk", {"place_id": place_id}, "name")
    if existing_name:
        frappe.db.set_value("Competitor Kiosk", existing_name, {
            "brand": operator_name,
            "display_name": display_name,
            "address": address,
            "city": city,
            "state_code": state,
            "zip_code": zip_code,
            "actual_zip_code": place_zip or "",
            "latitude": float(lat) if lat is not None else None,
            "longitude": float(lng) if lng is not None else None,
            "source": "google_places",
            "active": 1,
            "last_seen_on": now,
        })
        return False

    doc = frappe.new_doc("Competitor Kiosk")
    doc.place_id = place_id
    doc.brand = operator_name
    doc.display_name = display_name
    doc.address = address
    doc.city = city
    doc.state_code = state
    doc.zip_code = zip_code
    doc.actual_zip_code = place_zip or ""
    doc.latitude = float(lat) if lat is not None else None
    doc.longitude = float(lng) if lng is not None else None
    doc.source = "google_places"
    doc.active = 1
    doc.first_seen_on = now
    doc.last_seen_on = now
    doc.insert(ignore_permissions=True)
    return True


def _upsert_competitor_osm(operator_name: str, osm_place: Dict[str, Any], fallback_zip: str) -> bool:
    """
    Requires Competitor Kiosk fields:
      - osm_id (unique)
      - provider (optional)
    """
    osm_id = osm_place.get("osm_id")
    if not osm_id:
        return False

    display_name = (osm_place.get("display_name") or "").strip()
    address = (osm_place.get("address") or "").strip()
    city = (osm_place.get("city") or "").strip()
    state = (osm_place.get("state_code") or "").strip()
    place_zip = (osm_place.get("zip_code") or "").strip()
    zip_code = _z5(place_zip or fallback_zip)

    lat = osm_place.get("latitude")
    lng = osm_place.get("longitude")

    now = now_datetime()

    # If you add osm_id field:
    existing_name = None
    if frappe.get_meta("Competitor Kiosk").has_field("osm_id"):
        existing_name = frappe.db.get_value("Competitor Kiosk", {"osm_id": osm_id}, "name")
    else:
        # fallback: store osm_id in place_id with prefix (not ideal but works)
        existing_name = frappe.db.get_value("Competitor Kiosk", {"place_id": osm_id}, "name")

    if existing_name:
        update = {
            "brand": operator_name,
            "display_name": display_name,
            "address": address,
            "city": city,
            "state_code": state,
            "zip_code": zip_code,
            "latitude": float(lat) if lat is not None else None,
            "longitude": float(lng) if lng is not None else None,
            "source": "osm_overpass",
            "active": 1,
            "last_seen_on": now,
        }
        if frappe.get_meta("Competitor Kiosk").has_field("osm_id"):
            update["osm_id"] = osm_id
        if frappe.get_meta("Competitor Kiosk").has_field("provider"):
            update["provider"] = "osm_overpass"

        frappe.db.set_value("Competitor Kiosk", existing_name, update)
        return False

    doc = frappe.new_doc("Competitor Kiosk")

    if frappe.get_meta("Competitor Kiosk").has_field("osm_id"):
        doc.osm_id = osm_id
        doc.place_id = osm_id  # optional; keeps autoname stable if you ever switch
    else:
        doc.place_id = osm_id  # fallback mode

    if frappe.get_meta("Competitor Kiosk").has_field("provider"):
        doc.provider = "osm_overpass"

    doc.brand = operator_name
    doc.display_name = display_name
    doc.address = address
    doc.city = city
    doc.state_code = state
    doc.zip_code = zip_code
    doc.source = "osm_overpass"
    doc.active = 1
    doc.first_seen_on = now
    doc.last_seen_on = now

    doc.latitude = float(lat) if lat is not None else None
    doc.longitude = float(lng) if lng is not None else None

    doc.insert(ignore_permissions=True)
    return True


# ----------------------------
# Public: Run jobs
# ----------------------------
@frappe.whitelist()
def run_competitor_for_zip(zip_code: str) -> Dict[str, Any]:
    """
    Debug helper: scans ONE zip using BOTH Google + OSM.
    """
    zip_code = _z5(zip_code)

    zr = frappe.get_all(
        "Zip Code Analytics",
        fields=["zip_code", "latitude", "longitude"],
        filters={"zip_code": zip_code, "latitude": ["is", "set"], "longitude": ["is", "set"]},
        limit_page_length=1,
    )
    if not zr:
        return {"ok": False, "msg": "ZIP not found or missing lat/lng", "zip_code": zip_code}

    cfg = frappe.get_single("ATM Criteria")
    operator_names = _get_operator_companies()

    lat = float(zr[0]["latitude"])
    lng = float(zr[0]["longitude"])

    radius_m = int(cfg.get("places_radius_m") or 12000)
    max_results = int(cfg.get("max_places_per_type") or 10)

    created = 0
    scanned = 0

    # 1) Google
    try:
        api_key = _get_places_key()
        places, used_query = _search_google_competitor(api_key, operator_names, zip_code, lat, lng, radius_m, max_results)
        for p in places:
            scanned += 1
            display_name = ((p.get("displayName") or {}).get("text") or "").strip()
            address = (p.get("formattedAddress") or "").strip()
            operator = _infer_operator(display_name, address, operator_names)
            if _upsert_competitor_google(operator, p, fallback_zip=zip_code):
                created += 1
            time.sleep(0.1)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Google competitor scan failed")

    # 2) OSM Overpass
    osm_els = _search_osm_bitcoin_atms(lat, lng, max(radius_m, 20000))
    for el in osm_els:
        osm_place = _osm_element_to_place(el)
        operator = _infer_operator(osm_place.get("display_name"), osm_place.get("address"), operator_names)
        if osm_place.get("operator_hint"):
            # use operator_hint as extra signal
            operator = _infer_operator(osm_place.get("operator_hint"), osm_place.get("display_name"), operator_names)

        scanned += 1
        if _upsert_competitor_osm(operator, osm_place, fallback_zip=zip_code):
            created += 1
        time.sleep(0.05)

    frappe.db.commit()
    return {
        "ok": True,
        "zip_code": zip_code,
        "places_scanned_total": scanned,
        "competitor_created": created,
        "operators_loaded": len(operator_names),
    }


@frappe.whitelist()
def run_competitor_batch(batch_size: int = None) -> Dict[str, Any]:
    """
    Scheduler batch:
    - Uses ATM Criteria.last_zip_cursor_competitor and competitor_batch_size
    - Scans next N zips
    - Uses BOTH sources:
        Google Places (paid)
        OSM Overpass (free)
    - Upserts Competitor Kiosk
    """
    cfg = frappe.get_single("ATM Criteria")
    if not int(cfg.get("enabled") or 0):
        return {"ok": False, "msg": "ATM Criteria disabled"}

    cursor = cfg.get("last_zip_cursor_competitor") or "00000"
    bs = int(batch_size or (cfg.get("competitor_batch_size") or 1))

    operator_names = _get_operator_companies()
    radius_m = int(cfg.get("places_radius_m") or 12000)
    max_results = int(cfg.get("max_places_per_type") or 10)

    zips = _get_next_zip_batch(cursor, bs)

    created = 0
    scanned = 0

    # Google key loaded once
    api_key = None
    try:
        api_key = _get_places_key()
    except Exception:
        # allow OSM-only mode if Google key missing
        api_key = None

    for zr in zips:
        zc = zr["zip_code"]
        lat = float(zr["latitude"])
        lng = float(zr["longitude"])

        # 1) Google (paid) - keep quota safe: only do 1 search per ZIP (generic-first strategy)
        if api_key:
            places, used_query = _search_google_competitor(api_key, operator_names, zc, lat, lng, radius_m, max_results)
            for p in places:
                scanned += 1
                display_name = ((p.get("displayName") or {}).get("text") or "").strip()
                address = (p.get("formattedAddress") or "").strip()
                operator = _infer_operator(display_name, address, operator_names)
                if _upsert_competitor_google(operator, p, fallback_zip=zc):
                    created += 1
                time.sleep(0.15)

        # 2) OSM (free) - broaden radius a little
        osm_els = _search_osm_bitcoin_atms(lat, lng, max(radius_m, 20000))
        for el in osm_els:
            osm_place = _osm_element_to_place(el)
            operator = _infer_operator(osm_place.get("display_name"), osm_place.get("address"), operator_names)
            if osm_place.get("operator_hint"):
                operator = _infer_operator(osm_place.get("operator_hint"), osm_place.get("display_name"), operator_names)

            scanned += 1
            if _upsert_competitor_osm(operator, osm_place, fallback_zip=zc):
                created += 1
            time.sleep(0.05)

    new_cursor = zips[-1]["zip_code"] if zips else _z5(cursor)
    cfg.db_set("last_zip_cursor_competitor", new_cursor)

    frappe.db.commit()
    return {
        "ok": True,
        "zips_scanned": len(zips),
        "places_scanned_total": scanned,
        "competitor_created": created,
        "cursor_from": _z5(cursor),
        "cursor_to": new_cursor,
        "operators_loaded": len(operator_names),
        "google_enabled": bool(api_key),
    }


def run_competitor_minutely():
    """
    Legacy scheduler entrypoint.
    Kept for compatibility; the smarter scheduler now runs through
    cclms.services.zipintel.intelligence.run_five_minute_intelligence.
    """
    try:
        run_competitor_batch(batch_size=20)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Competitor minutely agent failed")


@frappe.whitelist()
def deactivate_stale_competitors(days_old: int = 120) -> Dict[str, Any]:
    """
    Optional maintenance:
    mark competitor kiosks inactive if not seen for N days.
    """
    cutoff = add_days(now_datetime(), -int(days_old))
    res = frappe.db.sql(
        """
        UPDATE `tabCompetitor Kiosk`
        SET active = 0
        WHERE active = 1
          AND last_seen_on IS NOT NULL
          AND last_seen_on < %s
        """,
        (cutoff,),
    )
    frappe.db.commit()
    return {"ok": True, "days_old": int(days_old)}
