import frappe

def _safe_date_field(df: str) -> str:
    # fallback to creation if the custom field doesn't exist
    if frappe.db.has_column("ATM Leads", df):
        return df
    return "creation"

@frappe.whitelist()
def get_workflow_summary(start_date=None, end_date=None, company=None, executive_name=None, date_field="sign_date"):
    """
    Count leads grouped by workflow_state.
    Date filter is applied to the selected event date field (default: sign_date).
    """
    df = _safe_date_field(date_field)

    conds = []
    vals = []

    if company:
        conds.append("company = %s")
        vals.append(company)

    if executive_name:
        conds.append("executive_name = %s")
        vals.append(executive_name)

    if start_date and end_date:
        conds.append(f"COALESCE({df}, creation) BETWEEN %s AND %s")
        vals.extend([start_date, end_date])

    where_sql = f"WHERE {' AND '.join(conds)}" if conds else ""

    sql = f"""
        SELECT IFNULL(workflow_state,'Unknown') AS state, COUNT(name) AS total
        FROM `tabATM Leads`
        {where_sql}
        GROUP BY state
    """
    rows = frappe.db.sql(sql, values=vals, as_dict=True)
    summary = {r.state: int(r.total) for r in rows}
    total = sum(summary.values())
    return {"summary": summary, "total": total}
