import frappe

def _safe_col(df: str) -> str:
    return df if frappe.db.has_column("ATM Leads", df) else "creation"

@frappe.whitelist(allow_guest=True)
def get_workflow_summary(
    start_date=None, end_date=None,
    company=None, executive_name=None,
    date_field="post_date"
):
    """
    Returns:
      {
        "summary": {state: count, ...},   # Draft excluded in UI, not here
        "total_all": int,                 # STRICT post_date total (matches your 1012)
        "filters": {...}
      }
    """
    df = _safe_col(date_field)  # expected "post_date"
    conds, vals = [], []
    if company:
        conds.append("company = %s");        vals.append(company)
    if executive_name:
        conds.append("executive_name = %s"); vals.append(executive_name)

    # --- TOTAL (strict post_date window) ---
    total_sql_where, total_vals = list(conds), list(vals)
    if start_date and end_date:
        total_sql_where.append(f"{df} BETWEEN %s AND %s")
        total_vals.extend([start_date, end_date])

    total_all = frappe.db.sql(
        f"SELECT COUNT(name) FROM `tabATM Leads`"
        + (" WHERE " + " AND ".join(total_sql_where) if total_sql_where else ""),
        values=total_vals
    )[0][0]

    # --- SUMMARY BY STATE (on same post_date window) ---
    sum_conds, sum_vals = list(conds), list(vals)
    if start_date and end_date:
        sum_conds.append(f"{df} BETWEEN %s AND %s")
        sum_vals.extend([start_date, end_date])

    rows = frappe.db.sql(
        f"""
        SELECT IFNULL(workflow_state, 'Unknown') AS state, COUNT(name) AS total
        FROM `tabATM Leads`
        {"WHERE " + " AND ".join(sum_conds) if sum_conds else ""}
        GROUP BY state
        """,
        values=sum_vals,
        as_dict=True
    )
    summary = {r.state: int(r.total) for r in rows}

    return {
        "summary": summary,
        "total_all": int(total_all),
        "filters": {
            "start_date": start_date, "end_date": end_date,
            "company": company, "executive_name": executive_name, "date_field": df
        }
    }
