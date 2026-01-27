import frappe

@frappe.whitelist(allow_guest=True)
def whoami():
    user = frappe.session.user or "Guest"
    if user == "Guest":
        return {"user": "Guest", "full_name": None, "roles": []}

    # roles works for normal users
    roles = frappe.get_roles(user)

    # full name without needing /api/resource/User permission
    full_name = frappe.db.get_value("User", user, "full_name") or user

    return {"user": user, "full_name": full_name, "roles": roles}
