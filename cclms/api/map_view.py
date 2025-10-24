import frappe
from frappe import _
from typing import List, Dict
from frappe.query_builder import DocType
from pypika import Order

def _normalize_bounds(north: float, south: float, east: float, west: float):
    """Normalize and return (north, south, east, west, crosses_antimeridian: bool)."""
    north = float(north); south = float(south); east = float(east); west = float(west)
    if north < south:
        north, south = south, north
    crosses = west > east
    return north, south, east, west, crosses


# ---------- Competitors ----------
@frappe.whitelist()
def get_competitors_in_viewport(north: float, south: float, east: float, west: float) -> List[Dict]:
    north, south, east, west, crosses = _normalize_bounds(north, south, east, west)

    CK = DocType("Competitor Kiosk")

    def run(cond):
        q = (
            frappe.qb.from_(CK)
            .select(CK.place_id.as_("id"), CK.brand, CK.zip_code, CK.latitude, CK.longitude)
            .where((CK.latitude >= south) & (CK.latitude <= north) & cond)
            .orderby(CK.modified, order=Order.desc)
            .limit(5000)
        )
        return frappe.db.sql(q.get_sql(), as_dict=True)

    if not crosses:
        return run((CK.longitude >= west) & (CK.longitude <= east))
    else:
        a = run(CK.longitude >= west)
        b = run(CK.longitude <= east)
        out = a + b
        # optional: de-duplicate on id
        seen = set(); dedup = []
        for r in out:
            k = r.get("id") or (r.get("latitude"), r.get("longitude"))
            if k in seen: continue
            seen.add(k); dedup.append(r)
        return dedup


# ---------- Places ----------
@frappe.whitelist()
def get_places_in_viewport(north: float, south: float, east: float, west: float) -> List[Dict]:
    north, south, east, west, crosses = _normalize_bounds(north, south, east, west)

    P = DocType("Place")

    def run(cond):
        q = (
            frappe.qb.from_(P)
            .select(P.name.as_("id"), P.name, P.business_type, P.zip_code, P.latitude, P.longitude)
            .where((P.latitude >= south) & (P.latitude <= north) & cond)
            .orderby(P.modified, order=Order.desc)
            .limit(5000)
        )
        return frappe.db.sql(q.get_sql(), as_dict=True)

    if not crosses:
        return run((P.longitude >= west) & (P.longitude <= east))
    else:
        a = run(P.longitude >= west)
        b = run(P.longitude <= east)
        out = a + b
        # optional: de-duplicate on id
        seen = set(); dedup = []
        for r in out:
            k = r.get("id") or (r.get("latitude"), r.get("longitude"))
            if k in seen: continue
            seen.add(k); dedup.append(r)
        return dedup

# import frappe
# from frappe import _
# from typing import List, Dict

# @frappe.whitelist()
# def get_competitors_in_viewport(north: float, south: float, east: float, west: float) -> List[Dict]:
#     """
#     Return competitor kiosks within map bounds.
#     WHERE:
#       latitude  BETWEEN south AND north
#       longitude BETWEEN west  AND east     (or wrap around anti-meridian)
#     """
#     try:
#         north = float(north); south = float(south)
#         east  = float(east);  west  = float(west)
#     except Exception:
#         frappe.throw(_("Invalid bounds"))

#     if north < south:
#         north, south = south, north

#     fields = ["place_id as id", "brand", "zip_code", "latitude", "longitude"]
#     lat_filter = ["between", [south, north]]

#     # west > east means the viewport crosses the anti-meridian (e.g., Pacific view)
#     if west <= east:
#         rows = frappe.get_all(
#             "Competitor Kiosk",
#             fields=fields,
#             filters={
#                 "latitude": lat_filter,
#                 "longitude": ["between", [west, east]],
#             },
#             order_by="modified desc",
#             limit_page_length=5000,
#         )
#     else:
#         left = frappe.get_all(
#             "Competitor Kiosk",
#             fields=fields,
#             filters={
#                 "latitude": lat_filter,
#                 "longitude": [">=", west],
#             },
#             order_by="modified desc",
#             limit_page_length=2500,
#         )
#         right = frappe.get_all(
#             "Competitor Kiosk",
#             fields=fields,
#             filters={
#                 "latitude": lat_filter,
#                 "longitude": ["<=", east],
#             },
#             order_by="modified desc",
#             limit_page_length=2500,
#         )
#         rows = left + right

#     # Defensive: filter out null coords
#     return [r for r in rows if r.get("latitude") is not None and r.get("longitude") is not None]

# @frappe.whitelist()
# def get_places_in_viewport(north: float, south: float, east: float, west: float, business_type: str | None = None):
#     """
#     Return scraped / stored places (candidate business locations) inside bounds.
#     Adjust the DOCTYPE + field names below to match your repo if different.
#     """
#     try:
#         north = float(north); south = float(south)
#         east  = float(east);  west  = float(west)
#     except Exception:
#         frappe.throw(_("Invalid bounds"))

#     if north < south:
#         north, south = south, north

#     # Pick the doctype that holds your scraped places.
#     # If your repo uses a different one (e.g., "Candidate Location"), change here.
#     PLACE_DOTYPE = "Place"

#     # If the doctype name differs in your app, try common fallbacks
#     if not frappe.db.table_exists(f"tab{PLACE_DOTYPE}"):
#         for alt in ("Candidate Location", "Business Place", "Business Location"):
#             if frappe.db.table_exists(f"tab{alt}"):
#                 PLACE_DOTYPE = alt
#                 break

#     fields = ["name as id", "name", "business_type", "zip_code", "latitude", "longitude"]
#     lat_filter = ["between", [south, north]]

#     def _query(extra_filters: dict):
#         return frappe.get_all(
#             PLACE_DOTYPE,
#             fields=fields,
#             filters=extra_filters,
#             order_by="modified desc",
#             limit_page_length=5000
#         )

#     def _merge(a, b):
#         return a + b

#     base_filters = {"latitude": lat_filter}
#     if business_type:
#         base_filters["business_type"] = business_type

#     if west <= east:
#         rows = _query({**base_filters, "longitude": ["between", [west, east]]})
#     else:
#         left  = _query({**base_filters, "longitude": [">=", west]})
#         right = _query({**base_filters, "longitude": ["<=", east]})
#         rows  = _merge(left, right)

#     return [r for r in rows if r.get("latitude") is not None and r.get("longitude") is not None]
