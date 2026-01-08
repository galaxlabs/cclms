import frappe
from frappe import _
import requests

# ---------- helpers ----------

def _google_key():
    return frappe.db.get_single_value("Google Maps Settings", "api_key")

def _safe_zip(z):
    if not z:
        return ""
    z = str(z).strip()
    # keep 5-char “ZIP” for US, don’t over-pad if non-US – we still LPAD in SQL
    return z.zfill(5) if z.isdigit() else z

# Geocode a single lead row into latitude/longitude using address fields
def _geocode_lead_row(row):
    key = _google_key()
    if not key:
        return None
    # build a best-effort address
    address = row.get("full_address") or row.get("address") or row.get("business_name") or ""
    city    = row.get("city") or ""
    state   = row.get("state") or row.get("state_code") or ""
    zipc    = row.get("zip_code") or row.get("zip") or ""
    country = row.get("country") or "USA"

    q = ", ".join([p for p in [address, city, state, _safe_zip(zipc), country] if p])
    if not q:
        return None

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": q, "key": key},
            timeout=12
        ).json()
        res = (resp.get("results") or [])
        if not res:
            return None
        loc = res[0].get("geometry", {}).get("location", {})
        lat, lng = loc.get("lat"), loc.get("lng")
        if lat is None or lng is None:
            return None
        return float(lat), float(lng)
    except Exception:
        return None


# ---------- whitelisted methods you already call from JS ----------

@frappe.whitelist()
def get_google_maps_settings():
    api_key = _google_key()
    map_id  = None
    try:
        map_id = frappe.db.get_single_value("Google Maps Settings", "map_id")
    except Exception:
        pass
    return {"api_key": api_key, "map_id": map_id}


@frappe.whitelist()
def get_zip_circles():
    """
    Returns centroid circles for Zip Code Analytics.
    - No hard dependency on 'radius_meters' column.
    - Computes a friendly radius from square_miles; defaults to ~8km.
    """
    dt = "Zip Code Analytics"
    meta = frappe.get_meta(dt)

    def has(field):
        try: return bool(meta.get_field(field))
        except Exception: return False

    base = ["zip_code", "latitude", "longitude"]
    optional = ["zone_color", "zone", "square_miles", "population",
                "margin", "competitor_kiosks", "zip_score", "state_code"]
    fields = base + [f for f in optional if has(f)]

    rows = frappe.get_all(dt, fields=fields, limit_page_length=200000)

    out = []
    import math
    for r in rows:
        lat, lng = r.get("latitude"), r.get("longitude")
        if lat is None or lng is None:
            continue
        sqmi = r.get("square_miles")
        if sqmi:
            try:
                eq_r_m = math.sqrt(float(sqmi)/math.pi) * 1609.34
                radius = int(max(5_000, min(25_000, eq_r_m * 2)))
            except Exception:
                radius = 8_000
        else:
            radius = 8_000

        out.append({
            "zip_code": r.get("zip_code"),
            "zone_color": r.get("zone_color") or r.get("zone") or "Unclassified",
            "latitude": float(lat), "longitude": float(lng),
            "radius_meters": radius,
            "population": r.get("population"),
            "margin": r.get("margin"),
            "competitor_kiosks": r.get("competitor_kiosks"),
            "zip_score": r.get("zip_score"),
            "state_code": r.get("state_code"),
        })
    return out


@frappe.whitelist()
def get_leads_non_red(filter_non_red: int = 0, us_only: int = 0, limit: int = 50000):
    params = {}
    conds = ["l.name is not null"]
    if int(us_only or 0):
        conds.append("(l.country is null or l.country = 'USA')")
    where_sql = " and ".join(conds)

    rows = frappe.db.sql(
        f"""
        select
          l.name,
          l.business_name,
          l.business_type,
          l.workflow_state,
          l.zip_code as zip,          -- <— use ONLY zip_code
          l.latitude,
          l.longitude
        from `tabATM Leads` l
        where {where_sql}
        order by l.modified desc
        limit %(lim)s
        """,
        {"lim": int(limit)},
        as_dict=True,
    )

    # zone map (optional) — pad ZIP safely
    zmap = {}
    if int(filter_non_red or 0):
        zrows = frappe.get_all("Zip Code Analytics",
                               fields=["zip_code", "zone_color"],
                               limit_page_length=200000)
        zmap = {str(r["zip_code"]).zfill(5): (r.get("zone_color") or "") for r in zrows}

    out = []
    for r in rows:
        lat, lng = r.get("latitude"), r.get("longitude")
        if lat is None or lng is None:
            got = _geocode_lead_row(r)     # best-effort geocode once
            if got:
                lat, lng = got
                try:
                    frappe.db.set_value("ATM Leads", r["name"],
                                        {"latitude": lat, "longitude": lng})
                except Exception:
                    pass
        if lat is None or lng is None:
            continue

        z = (str(r.get("zip") or "").strip().zfill(5)) if (r.get("zip") or "").strip().isdigit() else (r.get("zip") or "")
        zone = zmap.get(z, "") if zmap else ""
        if int(filter_non_red or 0) and zone == "Red":
            continue

        out.append({
            "name": r["name"],
            "business_name": r.get("business_name") or r["name"],
            "business_type": r.get("business_type") or "",
            "workflow_state": r.get("workflow_state") or "",
            "zip": z,
            "zone_color": zone,
            "latitude": float(lat),
            "longitude": float(lng),
        })
    return out


@frappe.whitelist()
def get_leads_in_viewport(north: float, south: float, east: float, west: float,
                          filter_non_red: int = 0, us_only: int = 0, limit: int = 50000):
    north, south = float(north), float(south)
    east, west   = float(east), float(west)

    params = {"n": north, "s": south}
    if west <= east:
        lng_cond = "l.longitude between %(w)s and %(e)s"
        params["w"] = west; params["e"] = east
    else:
        lng_cond = "(l.longitude >= %(w)s or l.longitude <= %(e)s)"
        params["w"] = west; params["e"] = east

    conds = [
        "l.latitude between %(s)s and %(n)s",
        lng_cond
    ]
    if int(us_only or 0):
        conds.append("(l.country is null or l.country = 'USA')")

    where_sql = " and ".join(conds)

    rows = frappe.db.sql(
        f"""
        select
          l.name,
          l.business_name,
          l.business_type,
          l.workflow_state,
          l.zip_code as zip,          -- <— use ONLY zip_code
          l.latitude,
          l.longitude
        from `tabATM Leads` l
        where {where_sql}
        order by l.modified desc
        limit %(lim)s
        """,
        {**params, "lim": int(limit)},
        as_dict=True,
    )

    zmap = {}
    if int(filter_non_red or 0):
        zrows = frappe.get_all("Zip Code Analytics",
                               fields=["zip_code", "zone_color"],
                               limit_page_length=200000)
        zmap = {str(r["zip_code"]).zfill(5): (r.get("zone_color") or "") for r in zrows}

    out = []
    for r in rows:
        lat, lng = r.get("latitude"), r.get("longitude")
        if lat is None or lng is None:
            continue

        z = (str(r.get("zip") or "").strip().zfill(5)) if (r.get("zip") or "").strip().isdigit() else (r.get("zip") or "")
        zone = zmap.get(z, "") if zmap else ""
        if int(filter_non_red or 0) and zone == "Red":
            continue

        out.append({
            "name": r["name"],
            "business_name": r.get("business_name") or r["name"],
            "business_type": r.get("business_type") or "",
            "workflow_state": r.get("workflow_state") or "",
            "zip": z,
            "zone_color": zone,
            "latitude": float(lat),
            "longitude": float(lng),
        })
    return out


@frappe.whitelist()
def geocode_missing_zip_centroids(limit: int = 500):
    """
    Convenience: fill Zip Code Analytics lat/lng for rows that are missing.
    Tries Google Geocoding with 'ZIP USA'.
    """
    key = _google_key()
    if not key:
        frappe.throw("Google Maps API key missing in Google Maps Settings")

    missing = frappe.get_all("Zip Code Analytics",
                             filters=[["latitude", "is", "not set"], ["zip_code", "is", "set"]],
                             fields=["name", "zip_code"],
                             limit_page_length=limit)
    upd = 0
    for r in missing:
        z = str(r["zip_code"]).zfill(5)
        try:
            j = requests.get("https://maps.googleapis.com/maps/api/geocode/json",
                             params={"address": f"{z} USA", "key": key, "components": f"postal_code:{z}|country:US"},
                             timeout=12).json()
            loc = (j.get("results") or [{}])[0].get("geometry", {}).get("location", {})
            lat, lng = loc.get("lat"), loc.get("lng")
            if lat is not None and lng is not None:
                frappe.db.set_value("Zip Code Analytics", r["name"],
                                    {"latitude": float(lat), "longitude": float(lng)})
                upd += 1
        except Exception:
            pass
    frappe.db.commit()
    return {"updated": upd}


# ---------------- Non-Red leads + type list (JOIN uses zip_code) ----------------
# @frappe.whitelist()
# def get_leads_non_red(filter_non_red: int = 1,
#                       workflow: str | None = None,
#                       business_types: list[str] | None = None,
#                       q: str | None = None):
#     """
#     Returns ATM Leads with lat/lng, joined to Zip Code Analytics for zone_color.
#     - filter_non_red=1 => only Green/Light Green/Yellow (exclude Red)
#     - workflow: exact workflow_state (optional)
#     - business_types: list of types to include (optional)
#     - q: free-text search over name/business_name/business_type/zip_code (optional)
#     """
#     params = {}
#     conds = ["l.latitude is not null", "l.longitude is not null"]

#     if int(filter_non_red or 0):
#         conds.append("(z.zone_color is null or z.zone_color <> 'Red')")

#     if workflow:
#         conds.append("l.workflow_state = %(wf)s")
#         params["wf"] = workflow

#     if business_types:
#         conds.append("l.business_type in %(types)s")
#         params["types"] = tuple(business_types)

#     if q:
#         params["q"] = f"%{q.strip()}%"
#         conds.append("("
#                      "l.name like %(q)s or "
#                      "l.business_name like %(q)s or "
#                      "l.business_type like %(q)s or "
#                      "l.zip_code like %(q)s"
#                      ")")

#     where_sql = " and ".join(conds)
#     rows = frappe.db.sql(
#         f"""
#         select
#             l.name,
#             l.business_name,
#             l.business_type,
#             l.workflow_state,
#             l.zip_code as zip,
#             l.latitude, l.longitude,
#             z.zone_color
#         from `tabATM Leads` l
#         left join `tabZip Code Analytics` z
#           on l.zip_code = z.zip_code
#         where {where_sql}
#         order by l.modified desc
#         limit 20000
#         """,
#         params,
#         as_dict=True,
#     )

#     out = []
#     for r in rows:
#         if r.get("latitude") is None or r.get("longitude") is None:
#             continue
#         out.append({
#             "name": r["name"],
#             "business_name": r.get("business_name") or r["name"],
#             "business_type": r.get("business_type") or "",
#             "workflow_state": r.get("workflow_state") or "",
#             "zip": r.get("zip") or "",
#             "zone_color": r.get("zone_color") or "",
#             "latitude": float(r["latitude"]),
#             "longitude": float(r["longitude"]),
#         })
#     return out

@frappe.whitelist()
def list_business_types(non_red_only: int = 1):
    cond = "and (z.zone_color is null or z.zone_color <> 'Red')" if int(non_red_only or 0) else ""
    rows = frappe.db.sql(
        f"""
        select distinct l.business_type
        from `tabATM Leads` l
        left join `tabZip Code Analytics` z
          on l.zip_code = z.zip_code
        where l.business_type is not null and l.business_type <> ''
        {cond}
        order by 1
        """,
        as_dict=True,
    )
    return [r["business_type"] for r in rows]
