import frappe

def _build_filters(args):
    filters = {}
    start = args.get("start_date")
    end = args.get("end_date")

    # Use creation if you don't have post_date
    if start and end:
        # If you have a date field like "post_date", switch to that
        filters["creation"] = ["between", [start, end]]

    if args.get("branch"):
        filters["branch"] = args["branch"]
    if args.get("company"):
        filters["company"] = args["company"]
    if args.get("executive_name"):
        filters["executive_name"] = args["executive_name"]
    return filters

@frappe.whitelist()
def get_workflow_summary(start_date=None, end_date=None, branch=None, company=None, executive_name=None):
    args = frappe._dict(
        start_date=start_date,
        end_date=end_date,
        branch=branch,
        company=company,
        executive_name=executive_name,
    )
    filters = _build_filters(args)

    # Use SQL for reliable GROUP BY across Frappe versions
    where, vals = frappe.db.build_conditions("ATM Leads", filters)
    sql = f"""
        SELECT IFNULL(workflow_state, 'Unknown') AS state, COUNT(name) AS total
        FROM `tabATM Leads`
        {f"WHERE {where}" if where else ""}
        GROUP BY state
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)
    summary = {r.state: int(r.total) for r in rows}

    total = frappe.db.count("ATM Leads", filters=filters)
    return {"summary": summary, "total": total}
import frappe

def _build_filters(args):
    filters = {}
    start = args.get("start_date")
    end = args.get("end_date")

    # Use creation if you don't have post_date
    if start and end:
        # If you have a date field like "post_date", switch to that
        filters["creation"] = ["between", [start, end]]

    if args.get("branch"):
        filters["branch"] = args["branch"]
    if args.get("company"):
        filters["company"] = args["company"]
    if args.get("executive_name"):
        filters["executive_name"] = args["executive_name"]
    return filters

@frappe.whitelist()
def get_workflow_summary(start_date=None, end_date=None, branch=None, company=None, executive_name=None):
    args = frappe._dict(
        start_date=start_date,
        end_date=end_date,
        branch=branch,
        company=company,
        executive_name=executive_name,
    )
    filters = _build_filters(args)

    # Use SQL for reliable GROUP BY across Frappe versions
    where, vals = frappe.db.build_conditions("ATM Leads", filters)
    sql = f"""
        SELECT IFNULL(workflow_state, 'Unknown') AS state, COUNT(name) AS total
        FROM `tabATM Leads`
        {f"WHERE {where}" if where else ""}
        GROUP BY state
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)
    summary = {r.state: int(r.total) for r in rows}

    total = frappe.db.count("ATM Leads", filters=filters)
    return {"summary": summary, "total": total}
import frappe

def _build_filters(args):
    filters = {}
    start = args.get("start_date")
    end = args.get("end_date")

    # Use creation if you don't have post_date
    if start and end:
        # If you have a date field like "post_date", switch to that
        filters["creation"] = ["between", [start, end]]

    if args.get("branch"):
        filters["branch"] = args["branch"]
    if args.get("company"):
        filters["company"] = args["company"]
    if args.get("executive_name"):
        filters["executive_name"] = args["executive_name"]
    return filters

@frappe.whitelist()
def get_workflow_summary(start_date=None, end_date=None, branch=None, company=None, executive_name=None):
    args = frappe._dict(
        start_date=start_date,
        end_date=end_date,
        branch=branch,
        company=company,
        executive_name=executive_name,
    )
    filters = _build_filters(args)

    # Use SQL for reliable GROUP BY across Frappe versions
    where, vals = frappe.db.build_conditions("ATM Leads", filters)
    sql = f"""
        SELECT IFNULL(workflow_state, 'Unknown') AS state, COUNT(name) AS total
        FROM `tabATM Leads`
        {f"WHERE {where}" if where else ""}
        GROUP BY state
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)
    summary = {r.state: int(r.total) for r in rows}

    total = frappe.db.count("ATM Leads", filters=filters)
    return {"summary": summary, "total": total}
import frappe

def _build_filters(args):
    filters = {}
    start = args.get("start_date")
    end = args.get("end_date")

    # Use creation if you don't have post_date
    if start and end:
        # If you have a date field like "post_date", switch to that
        filters["creation"] = ["between", [start, end]]

    if args.get("branch"):
        filters["branch"] = args["branch"]
    if args.get("company"):
        filters["company"] = args["company"]
    if args.get("executive_name"):
        filters["executive_name"] = args["executive_name"]
    return filters

@frappe.whitelist()
def get_workflow_summary(start_date=None, end_date=None, branch=None, company=None, executive_name=None):
    args = frappe._dict(
        start_date=start_date,
        end_date=end_date,
        branch=branch,
        company=company,
        executive_name=executive_name,
    )
    filters = _build_filters(args)

    # Use SQL for reliable GROUP BY across Frappe versions
    where, vals = frappe.db.build_conditions("ATM Leads", filters)
    sql = f"""
        SELECT IFNULL(workflow_state, 'Unknown') AS state, COUNT(name) AS total
        FROM `tabATM Leads`
        {f"WHERE {where}" if where else ""}
        GROUP BY state
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)
    summary = {r.state: int(r.total) for r in rows}

    total = frappe.db.count("ATM Leads", filters=filters)
    return {"summary": summary, "total": total}
