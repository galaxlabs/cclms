import frappe

def _safe_date_field(df: str) -> str:
    return df if frappe.db.has_column("ATM Leads", df) else "creation"

@frappe.whitelist(allow_guest=True)
def get_agent_performance(state="Signed", start_date=None, end_date=None, company=None, date_field="sign_date"):
    df = _safe_date_field(date_field)

    conds, vals = ["workflow_state = %s"], [state]
    if company:
        conds.append("company = %s"); vals.append(company)
    if start_date and end_date:
        conds.append(f"COALESCE({df}, creation) BETWEEN %s AND %s")
        vals.extend([start_date, end_date])

    where_sql = "WHERE " + " AND ".join(conds)
    sql = f"""
        SELECT executive_name, COUNT(name) AS total
        FROM `tabATM Leads`
        {where_sql}
        GROUP BY executive_name
        ORDER BY total DESC
    """
    rows = frappe.db.sql(sql, values=vals, as_dict=True)
    return {"state": state, "rows": rows}
