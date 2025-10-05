import frappe

@frappe.whitelist()
def get_agent_performance(state="Signed", start_date=None, end_date=None, branch=None, company=None):
    """
    Groups leads by executive_name for a given workflow_state (default 'Signed').
    Returns rows sorted by count desc.
    """
    filters = {}
    if state:
        filters["workflow_state"] = state
    if start_date and end_date:
        filters["post_date"] = ["between", [start_date, end_date]]
    if branch:
        filters["branch"] = branch
    if company:
        filters["company"] = company

    rows = frappe.get_all(
        "ATM Leads",
        filters=filters,
        fields=["executive_name", "count(name) as total"],
        group_by="executive_name",
        order_by="total desc"
    )

    return {
        "state": state,
        "rows": rows  # [{executive_name: "Ali", total: 7}, ...]
    }
