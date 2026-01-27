import frappe

@frappe.whitelist()
def get_all_zip_analytics(limit=1000):
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    limit = int(limit or 1000)

    rows = frappe.get_all(
        "Zip Code Analytics",
        fields=["name", "zip_code", "zip_score", "population", "kiosk_count", "competitor_count"],
        limit_page_length=limit,
        ignore_permissions=True,
    )
    return rows
