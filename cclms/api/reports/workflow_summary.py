import frappe
from frappe.utils import getdate, nowdate

# 1) Small helper to build flexible filters from incoming args.
def _build_filters(args):
    filters = {}

    # Date range: use "post_date" if present, else fallback to "creation"
    start = args.get("start_date")
    end = args.get("end_date")

    if start and end:
        # Frappe get_all supports "between" via filter lists
        filters["post_date"] = ["between", [start, end]]

    # Optional dimensions
    if args.get("branch"):
        filters["branch"] = args["branch"]
    if args.get("company"):
        filters["company"] = args["company"]
    if args.get("executive_name"):
        filters["executive_name"] = args["executive_name"]

    # Exclude Draft by default? Let caller decide. We'll not force it here.
    return filters

@frappe.whitelist()
def get_workflow_summary(start_date=None, end_date=None, branch=None, company=None, executive_name=None):
    """
    Returns counts by workflow_state and a grand total.
    Works over ATM Leads.
    """
    args = frappe._dict({
        "start_date": start_date,
        "end_date": end_date,
        "branch": branch,
        "company": company,
        "executive_name": executive_name
    })

    filters = _build_filters(args)

    # 2) Group-by workflow_state; Frappe supports group_by via "group_by" kwarg.
    rows = frappe.get_all(
        "ATM Leads",
        filters=filters,
        fields=["workflow_state", "count(name) as total"],
        group_by="workflow_state"
    )

    # 3) Normalize into a dict for easy UI consumption
    summary = { (r.workflow_state or "Unknown"): r.total for r in rows }

    # 4) Also compute overall total quickly
    total = frappe.db.count("ATM Leads", filters=filters)

    return {
        "summary": summary,    # {"Draft": 12, "Signed": 33, ...}
        "total": total
    }
