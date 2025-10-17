import frappe
from cclms.utils.zip_analytics import get_zip_row_by_zip  # You must implement this


def classify_zip(zip_code):
    """
    Returns zone name and color hex for a ZIP code.
    """
    row = get_zip_row_by_zip(zip_code)
    if not row:
        return "Unknown", "#888"  # fallback

    zone = classify_zip_row(row)
    color = {
        "Green": "#28a745",
        "Light Green": "#66bb6a",
        "Yellow": "#ffc107",
        "Red": "#dc3545"
    }.get(zone, "#888")

    return zone, color

def get_zip_row_by_zip(zip_code):
    """Fetch a record from Zip Code Analytics by zip"""
    doc = frappe.get_value("Zip Code Analytics", {"zip_code": zip_code}, "*", as_dict=True)
    return doc
