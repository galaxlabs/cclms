import frappe

@frappe.whitelist()
def get_operator_companies(limit=1000):
    # Token-auth users only; no Guest. (If you NEED Guest, add allow_guest=True)
    frappe.only_for("System Manager", "Administrator", "Sales User", "Sales Manager")

    limit = int(limit or 1000)

    rows = frappe.get_all(
        "Operator Companies",
        fields=["name"],
        limit_page_length=limit,
        ignore_permissions=True,  # we control access above
    )
    return rows
