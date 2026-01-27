import frappe
from cclms.utils.zip_classifier import classify_zip

@frappe.whitelist()
def get_map_data():
    leads = frappe.get_all(
        "ATM Leads",
        fields=["name", "zip_code", "latitude", "longitude", "company", "business_type"]
    )

    enriched = []
    for l in leads:
        zone, color = classify_zip(l.get("zip_code"))
        l["zone"] = zone
        l["color"] = color
        enriched.append(l)
    return enriched
