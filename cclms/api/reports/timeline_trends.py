import frappe

def _safe_date_field(df: str) -> str:
    return df if frappe.db.has_column("ATM Leads", df) else "creation"

@frappe.whitelist()
def get_timeline_trends(state="Signed", months=6, company=None, executive_name=None, date_field="sign_date"):
    df = _safe_date_field(date_field)
    date_expr = f"COALESCE({df}, creation)"

    conds, vals = ["workflow_state = %s"], [state]
    if company:
        conds.append("company = %s");        vals.append(company)
    if executive_name:
        conds.append("executive_name = %s"); vals.append(executive_name)

    where_sql = "WHERE " + " AND ".join(conds)
    sql = f"""
        SELECT DATE_FORMAT({date_expr}, '%%Y-%%m') AS bucket, COUNT(name) AS total
        FROM `tabATM Leads`
        {where_sql}
        GROUP BY bucket
        ORDER BY bucket DESC
        LIMIT {int(months)}
    """
    rows = frappe.db.sql(sql, values=vals, as_dict=True)
    rows.reverse()  # oldest → newest
    return {"state": state, "points": rows}
