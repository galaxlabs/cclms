import frappe

def _bbox_filters(north, south, east, west, lat_field="latitude", lng_field="longitude"):
    # Normal case: west < east (not crossing dateline)
    return {
        lat_field: ["between", [float(south), float(north)]],
        lng_field: ["between", [float(west), float(east)]],
    }

@frappe.whitelist()
def get_competitors_in_viewport(north: float, south: float, east: float, west: float, brand_exclude: str = "bitcoin depot", limit: int = 5000):
    f = _bbox_filters(north, south, east, west)
    rows = frappe.get_all(
        "Competitor Kiosk",
        fields=["place_id as id","brand","zip_code","latitude","longitude"],
        filters=f, limit_page_length=int(limit)
    )
    if brand_exclude:
        rows = [r for r in rows if brand_exclude.lower() not in (r["brand"] or "").lower()]
    return rows

@frappe.whitelist()
def get_places_in_viewport(north: float, south: float, east: float, west: float, business_type: str = "", limit: int = 5000):
    f = _bbox_filters(north, south, east, west)
    if business_type:
        f["business_type"] = business_type
    return frappe.get_all(
        "Place (Candidate Location)",
        fields=["place_id as id","name","business_type","zip_code","latitude","longitude","address"],
        filters=f, limit_page_length=int(limit)
    )

@frappe.whitelist()
def get_leads_in_viewport(north: float, south: float, east: float, west: float, workflow_states: list[str] | None = None, limit: int = 5000):
    f = _bbox_filters(north, south, east, west)
    if workflow_states:
        f["workflow_state"] = ["in", workflow_states]
    return frappe.get_all(
        "ATM Leads",
        fields=["name","business_name","workflow_state","zip","latitude","longitude","address","business_type"],
        filters=f, limit_page_length=int(limit)
    )

@frappe.whitelist()
def get_good_zips_in_viewport(north: float, south: float, east: float, west: float, include_yellow: int = 1, limit: int = 20000):
    f = _bbox_filters(north, south, east, west, lat_field="centroid_latitude", lng_field="centroid_longitude")
    zones = ["Green","Light Green"] + (["Yellow"] if int(include_yellow) else [])
    f["zone_color"] = ["in", zones]
    return frappe.get_all(
        "Zip Code Analytics",
        fields=["zip_code","zone_color","zip_score","centroid_latitude as latitude","centroid_longitude as longitude"],
        filters=f, limit_page_length=int(limit)
    )
