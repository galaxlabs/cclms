# cclms/api/atm_map.py
import json
import math
from typing import Any, Dict, List, Optional, Tuple
import requests
import frappe

# ---------------------------
# Config / External services
# ---------------------------
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
UA = "cclms-atm-radar/1.0 (+contact: admin@example.com)"  # <-- put your email/domain

def _google_key() -> Optional[str]:
    try:
        doc = frappe.get_single("Google Maps Settings")
        return getattr(doc, "api_key", None) or getattr(doc, "google_maps_api_key", None)
    except Exception:
        return frappe.conf.get("google_maps_api_key")

# ---------------------------
# Small helpers / cache
# ---------------------------
def _cache_get(key: str):
    return frappe.cache().get_value(key)

def _cache_set(key: str, val, ttl: int = 600):
    frappe.cache().set_value(key, val, expires_in_sec=ttl)

def _norm_bbox(bb: List[float]) -> Tuple[float, float, float, float]:
    # [south, west, north, east]
    s, w, n, e = [float(x) for x in bb]
    return s, w, n, e

def _doctype_exists(doctype: str) -> bool:
    try:
        return frappe.db.table_exists(f"tab{doctype}")
    except Exception:
        return False

def _field_exists(doctype: str, fieldname: str) -> bool:
    try:
        meta = frappe.get_meta(doctype)
        return any(df.fieldname == fieldname for df in meta.fields)
    except Exception:
        return False

def _pick_lead_doctype() -> Optional[str]:
    # Prefer custom doctype if present
    for dt in ("ATM Lead", "Atm Lead", "Lead"):
        if _doctype_exists(dt):
            return dt
    return None

def _coord_fields(doctype: str) -> Tuple[str, str]:
    candidates = [
        ("latitude", "longitude"),
        ("lat", "lng"),
        ("lat", "long"),
        ("geo_lat", "geo_lng"),
    ]
    for latf, lngf in candidates:
        if _field_exists(doctype, latf) and _field_exists(doctype, lngf):
            return latf, lngf
    return "latitude", "longitude"

def _address_fields(doctype: str) -> Dict[str, str]:
    # Map to likely fieldnames in your doctype
    fields = {
        "city": "city",
        "state": "state",
        "state_code": "state_code",
        "zip": "zip" if _field_exists(doctype, "zip") else "zip_code",
        "address": "address" if _field_exists(doctype, "address") else "address_line1",
    }
    return fields

def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.7613  # miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# ---------------------------
# Settings + States
# ---------------------------
@frappe.whitelist(allow_guest=True)
def get_settings() -> Dict[str, Any]:
    key = _google_key()
    if not key:
        frappe.throw("Google Maps API key not configured in 'Google Maps Settings' or site_config.")
    usa_bbox = [24.396308, -125.0, 49.384358, -66.93457]  # [S, W, N, E]
    return {"google_maps_api_key": key, "usa_bbox": usa_bbox}

US_STATES = [
    {"code": "AL", "name": "Alabama"}, {"code": "AK", "name": "Alaska"},
    {"code": "AZ", "name": "Arizona"}, {"code": "AR", "name": "Arkansas"},
    {"code": "CA", "name": "California"}, {"code": "CO", "name": "Colorado"},
    {"code": "CT", "name": "Connecticut"}, {"code": "DE", "name": "Delaware"},
    {"code": "FL", "name": "Florida"}, {"code": "GA", "name": "Georgia"},
    {"code": "HI", "name": "Hawaii"}, {"code": "ID", "name": "Idaho"},
    {"code": "IL", "name": "Illinois"}, {"code": "IN", "name": "Indiana"},
    {"code": "IA", "name": "Iowa"}, {"code": "KS", "name": "Kansas"},
    {"code": "KY", "name": "Kentucky"}, {"code": "LA", "name": "Louisiana"},
    {"code": "ME", "name": "Maine"}, {"code": "MD", "name": "Maryland"},
    {"code": "MA", "name": "Massachusetts"}, {"code": "MI", "name": "Michigan"},
    {"code": "MN", "name": "Minnesota"}, {"code": "MS", "name": "Mississippi"},
    {"code": "MO", "name": "Missouri"}, {"code": "MT", "name": "Montana"},
    {"code": "NE", "name": "Nebraska"}, {"code": "NV", "name": "Nevada"},
    {"code": "NH", "name": "New Hampshire"}, {"code": "NJ", "name": "New Jersey"},
    {"code": "NM", "name": "New Mexico"}, {"code": "NY", "name": "New York"},
    {"code": "NC", "name": "North Carolina"}, {"code": "ND", "name": "North Dakota"},
    {"code": "OH", "name": "Ohio"}, {"code": "OK", "name": "Oklahoma"},
    {"code": "OR", "name": "Oregon"}, {"code": "PA", "name": "Pennsylvania"},
    {"code": "RI", "name": "Rhode Island"}, {"code": "SC", "name": "South Carolina"},
    {"code": "SD", "name": "South Dakota"}, {"code": "TN", "name": "Tennessee"},
    {"code": "TX", "name": "Texas"}, {"code": "UT", "name": "Utah"},
    {"code": "VT", "name": "Vermont"}, {"code": "VA", "name": "Virginia"},
    {"code": "WA", "name": "Washington"}, {"code": "WV", "name": "West Virginia"},
    {"code": "WI", "name": "Wisconsin"}, {"code": "WY", "name": "Wyoming"},
    {"code": "DC", "name": "District of Columbia"},
]

@frappe.whitelist(allow_guest=True)
def list_us_states() -> Dict[str, Any]:
    return {"states": US_STATES}

# ---------------------------
# Overpass (public ATMs)
# ---------------------------
def _overpass_public(bb: Tuple[float, float, float, float]) -> Dict[str, Any]:
    s, w, n, e = bb
    bbox = f"{s},{w},{n},{e}"
    ql = f"""
[out:json][timeout:30];
(
  node["amenity"="atm"]["brand"~"Bitcoin",i]({bbox});
  node["amenity"="atm"]["operator"~"Bitcoin Depot|Localcoin|RockItCoin",i]({bbox});
  node["amenity"="atm"]["name"~"Bitcoin|BTC|Bitomat|Bancomat",i]({bbox});
  node["amenity"="atm"]["currency:XBT"="yes"]({bbox});
  node["amenity"="atm"]["payment:onchain"="yes"]({bbox});
  node["amenity"="atm"]["payment:lightning"="yes"]({bbox});
);
out tags center 4000;
"""
    r = requests.post(
        OVERPASS_URL,
        data={"data": ql},
        headers={"User-Agent": UA, "Accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()

def _elements_to_public(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for el in elements or []:
        eid = el.get("id")
        if eid in seen:
            continue
        seen.add(eid)
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {}) or {}
        out.append({
            "id": eid,
            "source": "osm",
            "lat": float(lat),
            "lon": float(lon),
            "name": tags.get("name") or tags.get("operator") or "Bitcoin ATM",
            "brand": tags.get("brand"),
            "operator": tags.get("operator"),
            "website": tags.get("website") or tags.get("url"),
            "opening_hours": tags.get("opening_hours"),
            "onchain": tags.get("payment:onchain") == "yes",
            "lightning": tags.get("payment:lightning") == "yes",
            "currency_xbt": tags.get("currency:XBT") == "yes",
            "address": {
                "street": tags.get("addr:street"),
                "housenumber": tags.get("addr:housenumber"),
                "city": tags.get("addr:city"),
                "state": tags.get("addr:state"),
                "postcode": tags.get("addr:postcode"),
            },
        })
    return out

# ---------------------------
# Leads by state (+ nearest ATM within 1 mile)
# ---------------------------
def _sql_where_for_state(doctype: str, state_code: str) -> str:
    F = _address_fields(doctype)
    st = F["state"]
    sc = F["state_code"]
    # match either code or name
    return f"(IFNULL({sc},'') = %(state_code)s OR IFNULL({st},'') = %(state_name)s)"

def _state_name_from_code(code: str) -> str:
    for x in US_STATES:
        if x["code"].lower() == code.lower():
            return x["name"]
    return code

@frappe.whitelist(allow_guest=True)
def get_leads_by_state(state_code: str, persist_geocode: Optional[str] = "false") -> Dict[str, Any]:
    """
    Returns your ATM leads for a US state, and tags each with `installed_within_mile`
    and nearest public ATM info if any is within 1 mile (~1609m).
    """
    if not state_code:
        frappe.throw("state_code is required (e.g., CA)")
    dt = _pick_lead_doctype()
    if not dt:
        return {"leads": [], "public": [], "bounds": None}

    latf, lngf = _coord_fields(dt)
    F = _address_fields(dt)
    where_state = _sql_where_for_state(dt, state_code)

    sql = f"""
        SELECT
          name,
          {latf} AS lat,
          {lngf} AS lon,
          IFNULL(workflow_state, IFNULL(status, '')) AS state,
          IFNULL(company, '') AS company,
          IFNULL(executive_name, '') AS executive_name,
          IFNULL({F['address']}, '') AS address,
          IFNULL({F['city']}, '') AS city,
          IFNULL({F['state']}, '') AS state_name,
          IFNULL({F['state_code']}, '') AS state_code,
          IFNULL({F['zip']}, '') AS zip
        FROM `tab{dt}`
        WHERE {where_state}
          AND (
            ({latf} IS NOT NULL AND {lngf} IS NOT NULL)
            OR (IFNULL({F['address']},'')!='' OR IFNULL({F['city']},'')!='' OR IFNULL({F['zip']},'')!='')
          )
        LIMIT 6000
    """
    rows = frappe.db.sql(
        sql,
        {"state_code": state_code, "state_name": _state_name_from_code(state_code)},
        as_dict=True,
    )

    # Geocode any rows missing lat/lon (optional)
    key = _google_key()
    do_geocode = bool(key) and str(persist_geocode).lower() == "true"
    geocoded = []
    for r in rows:
        if (r.lat is None or r.lon is None) and do_geocode:
            addr = ", ".join([x for x in [r.address, r.city, r.state_name or r.state_code, r.zip, "USA"] if x])
            try:
                g = requests.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={"address": addr, "key": key},
                    timeout=12,
                ).json()
                if g.get("status") == "OK" and g.get("results"):
                    loc = g["results"][0]["geometry"]["location"]
                    r.lat = float(loc["lat"])
                    r.lon = float(loc["lng"])
                    geocoded.append(r.name)
                    # persist back into doc if fields exist
                    try:
                        frappe.db.set_value(dt, r.name, {latf: r.lat, lngf: r.lon})
                    except Exception:
                        pass
            except Exception:
                pass

    # Convert to features + compute bounds
    leads: List[Dict[str, Any]] = []
    minlat = minlon = 999
    maxlat = maxlon = -999
    for r in rows:
        if r.lat is None or r.lon is None:
            continue
        lat = float(r.lat); lon = float(r.lon)
        minlat = min(minlat, lat); maxlat = max(maxlat, lat)
        minlon = min(minlon, lon); maxlon = max(maxlon, lon)
        leads.append({
            "id": r.name,
            "source": "lead",
            "lat": lat,
            "lon": lon,
            "state": r.state or "",
            "company": r.company or "",
            "executive_name": r.executive_name or "",
            "address": r.address or "",
            "city": r.city or "",
            "state_name": r.state_name or r.state_code or "",
            "zip": r.zip or "",
        })

    bounds = None
    if leads:
        # pad bounds a bit
        pad_lat = (maxlat - minlat) * 0.05 or 0.1
        pad_lon = (maxlon - minlon) * 0.05 or 0.1
        bounds = [minlat - pad_lat, minlon - pad_lon, maxlat + pad_lat, maxlon + pad_lon]

    # Pull public ATMs once for the state bounds (if we have leads), else for USA chunk around state code via cache
    public: List[Dict[str, Any]] = []
    if bounds:
        key_bb = tuple(bounds)
        cached = _cache_get(f"public_atm::{key_bb}")
        if cached:
            public = cached
        else:
            data = _overpass_public(_norm_bbox(bounds))
            public = _elements_to_public(data.get("elements", []))
            _cache_set(f"public_atm::{key_bb}", public, ttl=300)

    # For each lead, find nearest public ATM within 1 mile
    for L in leads:
        L["installed_within_mile"] = False
        L["nearest_public"] = None
        best = None
        best_d = 9e9
        for P in public:
            d = _haversine_miles(L["lat"], L["lon"], P["lat"], P["lon"])
            if d < best_d:
                best_d = d; best = P
        if best and best_d <= 1.0:
            L["installed_within_mile"] = True
            L["nearest_public"] = {
                "name": best.get("name"),
                "brand": best.get("brand"),
                "operator": best.get("operator"),
                "website": best.get("website"),
                "distance_miles": round(best_d, 2),
            }

    return {"leads": leads, "public": public, "bounds": bounds}

# ---------------------------
# Create Prospect from map
# ---------------------------
def _pick_target_prospect_doctype() -> str:
    for dt in ("ATM Prospect", "ATM Location", "Lead"):
        if _doctype_exists(dt):
            return dt
    return "Lead"

@frappe.whitelist(allow_guest=False)
def create_prospect_from_map(
    name: Optional[str] = None,
    brand: Optional[str] = None,
    operator: Optional[str] = None,
    website: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    address: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a prospect/lead/ATM Location from a public map item.
    """
    dt = _pick_target_prospect_doctype()
    doc = frappe.new_doc(dt)
    # best-effort mapping
    if hasattr(doc, "company_name"):
        doc.company_name = name or operator or brand or "Bitcoin ATM"
    elif hasattr(doc, "lead_name"):
        doc.lead_name = name or operator or brand or "Bitcoin ATM"
    elif hasattr(doc, "title"):
        doc.title = name or operator or brand or "Bitcoin ATM"
    if hasattr(doc, "website"): doc.website = website
    if hasattr(doc, "address"): doc.address = address
    if hasattr(doc, "city"): doc.city = city
    if hasattr(doc, "state"): doc.state = state
    if hasattr(doc, "zip") or hasattr(doc, "zip_code"):
        try:
            setattr(doc, "zip", zip)
        except Exception:
            setattr(doc, "zip_code", zip)
    # lat/lon if exist
    for latf, lngf in (("latitude","longitude"), ("lat","lng"), ("lat","long")):
        if hasattr(doc, latf) and hasattr(doc, lngf):
            setattr(doc, latf, lat)
            setattr(doc, lngf, lon)
            break
    # mark source
    if hasattr(doc, "source"): doc.source = "Map"
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"doctype": dt, "name": doc.name}
