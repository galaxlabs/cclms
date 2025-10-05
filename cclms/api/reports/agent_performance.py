import frappe

@frappe.whitelist()
def get_agent_performance(state="Signed", start_date=None, end_date=None, branch=None, company=None):
    filters = {}
    if state:
        filters["workflow_state"] = state
    if start_date and end_date:
        filters["creation"] = ["between", [start_date, end_date]]
    if branch:
        filters["branch"] = branch
    if company:
        filters["company"] = company

    where, vals = frappe.db.build_conditions("ATM Leads", filters)
    sql = f"""
        SELECT executive_name, COUNT(name) AS total
        FROM `tabATM Leads`
        {f"WHERE {where}" if where else ""}
        GROUP BY executive_name
        ORDER BY total DESC
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)
    return {"state": state, "rows": rows}
import frappe

@frappe.whitelist()
def get_agent_performance(state="Signed", start_date=None, end_date=None, branch=None, company=None):
    filters = {}
    if state:
        filters["workflow_state"] = state
    if start_date and end_date:
        filters["creation"] = ["between", [start_date, end_date]]
    if branch:
        filters["branch"] = branch
    if company:
        filters["company"] = company

    where, vals = frappe.db.build_conditions("ATM Leads", filters)
    sql = f"""
        SELECT executive_name, COUNT(name) AS total
        FROM `tabATM Leads`
        {f"WHERE {where}" if where else ""}
        GROUP BY executive_name
        ORDER BY total DESC
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)
    return {"state": state, "rows": rows}
import frappe

@frappe.whitelist()
def get_agent_performance(state="Signed", start_date=None, end_date=None, branch=None, company=None):
    filters = {}
    if state:
        filters["workflow_state"] = state
    if start_date and end_date:
        filters["creation"] = ["between", [start_date, end_date]]
    if branch:
        filters["branch"] = branch
    if company:
        filters["company"] = company

    where, vals = frappe.db.build_conditions("ATM Leads", filters)
    sql = f"""
        SELECT executive_name, COUNT(name) AS total
        FROM `tabATM Leads`
        {f"WHERE {where}" if where else ""}
        GROUP BY executive_name
        ORDER BY total DESC
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)
    return {"state": state, "rows": rows}
import frappe

@frappe.whitelist()
def get_agent_performance(state="Signed", start_date=None, end_date=None, branch=None, company=None):
    filters = {}
    if state:
        filters["workflow_state"] = state
    if start_date and end_date:
        filters["creation"] = ["between", [start_date, end_date]]
    if branch:
        filters["branch"] = branch
    if company:
        filters["company"] = company

    where, vals = frappe.db.build_conditions("ATM Leads", filters)
    sql = f"""
        SELECT executive_name, COUNT(name) AS total
        FROM `tabATM Leads`
        {f"WHERE {where}" if where else ""}
        GROUP BY executive_name
        ORDER BY total DESC
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)
    return {"state": state, "rows": rows}
