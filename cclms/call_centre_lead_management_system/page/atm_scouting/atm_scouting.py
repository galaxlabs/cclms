# apps/cclms/cclms/call_centre_lead_management_system/page/atm_scouting/atm_scouting.py
import frappe
from frappe import _

# ------------------------------
# Google Maps API Key
# ------------------------------
@frappe.whitelist()
def get_google_maps_key():
    """Return Google Maps API key from Single doctype."""
    key = frappe.db.get_single_value("Google Maps Settings", "api_key")
    return {"api_key": key}

# ------------------------------
# Leads for Map
# ------------------------------
@frappe.whitelist()
def get_leads_for_map():
    """Return ATM Leads with lat/lng + zone (uses your existing API if available)."""
    try:
        data = frappe.get_attr("cclms.api.map_data.get_map_data")() or []
        leads = []
        for l in data:
            leads.append({
                "name": l.get("name"),
                "business_name": l.get("business_name"),
                "business_type": l.get("business_type"),
                "workflow_state": l.get("workflow_state"),
                "zip": l.get("zip"),
                "zone": l.get("zone") or "Unclassified",
                "latitude": float(l.get("latitude")) if l.get("latitude") else None,
                "longitude": float(l.get("longitude")) if l.get("longitude") else None,
                "score": l.get("score")
            })
        return leads
    except Exception:
        # Fallback direct query
        fields = ["name","business_name","business_type","workflow_state","zip","zone","latitude","longitude"]
        leads = frappe.get_all("ATM Leads", fields=fields)
        for x in leads:
            x["latitude"] = float(x["latitude"]) if x.get("latitude") else None
            x["longitude"] = float(x["longitude"]) if x.get("longitude") else None
            x["zone"] = x.get("zone") or "Unclassified"
        return leads

# ------------------------------
# Zone Circles (defensive against missing fields)
# ------------------------------
@frappe.whitelist()
def get_zone_circles():
    """
    Return zip-level zone circles for overlays.
    - Queries only existing fields on Zip Code Analytics.
    - Computes competitor_kiosks = total_kiosks - company_kiosks when possible.
    - Uses centroid_latitude/longitude or falls back to latitude/longitude.
    - Derives radius from square_miles if radius_meters missing.
    """
    doctype = "Zip Code Analytics"
    meta = frappe.get_meta(doctype)

    def has(fieldname: str) -> bool:
        return any(df.fieldname == fieldname for df in meta.fields)

    # Pick lat/lng fields
    lat_field = "centroid_latitude" if has("centroid_latitude") else ("latitude" if has("latitude") else None)
    lng_field = "centroid_longitude" if has("centroid_longitude") else ("longitude" if has("longitude") else None)
    if not lat_field or not lng_field:
        return []

    # Safe field list
    fields = ["zip_code"]
    for f in ("zone", "population", "margin", "radius_meters", "square_miles",
              "total_kiosks", "company_kiosks"):
        if has(f):
            fields.append(f)
    fields.extend([lat_field, lng_field])

    rows = frappe.get_all(doctype, fields=fields, limit_page_length=20000)

    out = []
    for r in rows:
        lat = r.get(lat_field)
        lng = r.get(lng_field)
        if not lat or not lng:
            continue
        try:
            lat = float(lat); lng = float(lng)
        except Exception:
            continue

        # Compute competitors if we can
        competitor_kiosks = None
        if "total_kiosks" in r and "company_kiosks" in r:
            try:
                total_k = int(r.get("total_kiosks") or 0)
                our_k  = int(r.get("company_kiosks") or 0)
                competitor_kiosks = max(total_k - our_k, 0)
            except Exception:
                competitor_kiosks = None

        # Radius choice
        radius_meters = None
        if "radius_meters" in r and r.get("radius_meters"):
            try:
                radius_meters = float(r.get("radius_meters"))
            except Exception:
                radius_meters = None
        if not radius_meters and "square_miles" in r and r.get("square_miles"):
            try:
                import math
                area_mi2 = float(r.get("square_miles"))
                radius_meters = math.sqrt(max(area_mi2, 0.0) / math.pi) * 1609.34
            except Exception:
                radius_meters = None
        if not radius_meters:
            radius_meters = 8000  # ~5 miles

        out.append({
            "zip_code": r.get("zip_code"),
            "zone": (r.get("zone") or "Unclassified") if "zone" in r else "Unclassified",
            "population": r.get("population") if "population" in r else None,
            "margin": r.get("margin") if "margin" in r else None,
            "competitor_kiosks": competitor_kiosks,
            "latitude": lat,
            "longitude": lng,
            "radius_meters": radius_meters,
        })
    return out

# ------------------------------
# Create Lead from Map (with dedupe)
# ------------------------------
@frappe.whitelist()
def create_lead_from_map(lat: float, lng: float, formatted_address: str = "", zip: str = ""):
    """Create Draft ATM Lead at lat/lng if not near-duplicate."""
    lat = float(lat); lng = float(lng)

    near = nearest_existing_lead(lat, lng, radius_km=0.05)
    if near:
        frappe.throw(_("Lead already exists nearby: {0} ({1})").format(near.get("name"), near.get("workflow_state")))

    doc = frappe.get_doc({
        "doctype": "ATM Leads",
        "business_name": formatted_address or "Map Prospect",
        "address": formatted_address,
        "zip": zip,
        "latitude": lat,
        "longitude": lng,
        "workflow_state": "Draft"
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name}

# ------------------------------
# Helper: nearest lead (fixed filters)
# ------------------------------
def nearest_existing_lead(lat, lng, radius_km=0.05):
    """
    Bounding-box prefilter + haversine precise check.
    Uses list-of-lists filter syntax to avoid SQL generation issues.
    """
    lat = float(lat); lng = float(lng)
    lat_min = min(lat - 0.01, lat + 0.01)
    lat_max = max(lat - 0.01, lat + 0.01)
    lng_min = min(lng - 0.01, lng + 0.01)
    lng_max = max(lng - 0.01, lng + 0.01)

    filters = [
        ["ATM Leads", "latitude", "between", [lat_min, lat_max]],
        ["ATM Leads", "longitude", "between", [lng_min, lng_max]],
        ["ATM Leads", "latitude", "is", "set"],
        ["ATM Leads", "longitude", "is", "set"],
    ]

    leads = frappe.get_al_
