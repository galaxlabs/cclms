import frappe
from frappe.utils.data import flt

@frappe.whitelist()
def get_atm_map_data(state=None):
    """Return GeoJSON for ATM Leads + optional ZIP zone layers."""
    leads = frappe.db.get_all(
        "ATM Leads",
        fields=["name", "zone", "latitude", "longitude", "business_name", "business_type", "workflow_state", "zip"],
        filters={"latitude": ["is", "set"], "longitude": ["is", "set"]},
        limit_page_length=5000,
    )

    features = []
    color_map = {
        "Green": "#16a34a",
        "Light Green": "#86efac",
        "Yellow": "#facc15",
        "Red": "#ef4444",
        "Unclassified": "#9ca3af",
    }

    for l in leads:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [flt(l.longitude), flt(l.latitude)]},
            "properties": {
                "lead": l.name,
                "zone": l.zone or "Unclassified",
                "color": color_map.get(l.zone or "Unclassified"),
                "business": l.business_name,
                "type": l.business_type,
                "status": l.workflow_state,
                "zip": l.zip
            }
        })

    return {"type": "FeatureCollection", "features": features}
