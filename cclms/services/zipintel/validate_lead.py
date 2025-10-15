import frappe
from .rules import classify_zip

def validate_lead_zip(doc, _):
    """Attach zone and color to lead before saving; block Red if needed."""
    if not doc.zip:
        return
    zone, color = classify_zip(doc.zip)
    doc.zone = zone
    doc.zone_color = color  # add this field if not already there

    if zone == "Red":
        frappe.throw(f"Lead in ZIP {doc.zip} is not allowed (Red zone).")
