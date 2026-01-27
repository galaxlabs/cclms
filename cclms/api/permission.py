import frappe

def has_app_permission():
    """
    Return True/False for showing app icon to the user.
    Simple safe default: allow System Manager only, or allow all logged in users.
    """

    # Example 1: allow only System Manager
    return "System Manager" in frappe.get_roles()

    # Example 2 (open): allow everyone logged in
    # return not frappe.session.user == "Guest"
