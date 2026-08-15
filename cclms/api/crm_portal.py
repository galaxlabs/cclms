import frappe


@frappe.whitelist(allow_guest=True)
def get_current_sales_agent():
    """Return the current portal user's sales-agent context for the CRM Portal (xg-system).

    This is the CRM Portal (sales-agent) identity, separate from the operator portal.
    Resolves the Sales Agent record by the logged-in user's email / user link.
    """
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Authentication required", frappe.PermissionError)

    full_name = frappe.db.get_value("User", user, "full_name") or user
    roles = frappe.get_roles(user)

    sales_agent = None
    branch = None
    employee = None
    company = None
    if frappe.db.exists("DocType", "Sales Agent"):
        meta = frappe.get_meta("Sales Agent")
        fieldnames = {f.fieldname for f in meta.fields}
        sales_agent = frappe.db.get_value("Sales Agent", {"user": user}, "name") or None
        if not sales_agent and "email" in fieldnames:
            sales_agent = frappe.db.get_value("Sales Agent", {"email": user}, "name") or None
        if sales_agent:
            agent = frappe.get_doc("Sales Agent", sales_agent)
            branch = agent.get("branch")
            employee = agent.get("employee")
            company = agent.get("company")
            if not full_name or full_name == user:
                full_name = agent.get("full_name") or agent.get("agent_name") or full_name

    return {
        "is_authenticated": True,
        "user": user,
        "full_name": full_name,
        "roles": roles,
        "sales_agent": sales_agent,
        "branch": branch,
        "employee": employee,
        "company": company,
        "is_manager": "System Manager" in roles or "Sales Manager" in roles,
    }
