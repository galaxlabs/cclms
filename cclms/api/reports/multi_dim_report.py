import frappe

DIMENSIONS = {
    "company": "company",
    "agent": "COALESCE(NULLIF(executive_name,''),'Unassigned')",
    "state": "COALESCE(NULLIF(state_code,''),'')",
    "state_name": "COALESCE(NULLIF(state,''),'')",
    "branch": "COALESCE(NULLIF(branch,''),'')",
    "status": "COALESCE(NULLIF(workflow_state,''),'Unknown')",
    "month": "DATE_FORMAT(post_date, '%%Y-%%m')",
}

MEASURES = {
    "count": "COUNT(name)",
    "submitted": "COUNT(name)",
    "approved": "SUM(CASE WHEN workflow_state='Approved' THEN 1 ELSE 0 END)",
    "agreement_sent": "SUM(CASE WHEN workflow_state='Agreement Sent' THEN 1 ELSE 0 END)",
    "signed": "SUM(CASE WHEN workflow_state='Signed' THEN 1 ELSE 0 END)",
    "converted": "SUM(CASE WHEN workflow_state='Converted' THEN 1 ELSE 0 END)",
    "installed": "SUM(CASE WHEN workflow_state='Installed' THEN 1 ELSE 0 END)",
    "rejected": "SUM(CASE WHEN workflow_state='Rejected' THEN 1 ELSE 0 END)",
    "signed_rejected": "SUM(CASE WHEN workflow_state='Signed Rejected' THEN 1 ELSE 0 END)",
    "cancelled": "SUM(CASE WHEN workflow_state='Cancelled' THEN 1 ELSE 0 END)",
    "pending": "SUM(CASE WHEN workflow_state IN ('Pending','Submitted') THEN 1 ELSE 0 END)",
}


def _coerce_list(value):
    if isinstance(value, str):
        import json
        try:
            return json.loads(value)
        except Exception:
            return [value] if value else []
    return value or []


@frappe.whitelist(allow_guest=True)
def multi_dim_report(dimensions=None, measures=None, start_date=None, end_date=None, company=None, agent=None, state_code=None, status=None):
    """Generate a multi-dimensional ATM Leads report.

    - dimensions: list of dimension keys (company, agent, state, state_name, branch, status, month)
    - measures:    list of measure keys (count, submitted, approved, signed, converted, installed, rejected, signed_rejected, cancelled, pending)
    - Optional filters: company, agent, state_code, status, date range on post_date
    Returns rows grouped by the chosen dimensions with the chosen measures, plus dimension/measure metadata.
    """
    dims = _coerce_list(dimensions) or ["company"]
    measures = _coerce_list(measures) or ["count", "signed", "rejected"]

    dims = [d for d in dims if d in DIMENSIONS]
    measures = [m for m in measures if m in MEASURES]
    if not dims:
        dims = ["company"]

    conds, vals = ["docstatus < 2", "IFNULL(workflow_state,'') <> 'Draft'"], []
    if start_date and end_date:
        conds.append("post_date BETWEEN %s AND %s"); vals.extend([start_date, end_date])
    if company:
        conds.append("company = %s"); vals.append(company)
    if agent:
        conds.append("executive_name = %s"); vals.append(agent)
    if state_code:
        conds.append("state_code = %s"); vals.append(state_code)
    if status:
        conds.append("workflow_state = %s"); vals.append(status)

    dim_sql = ", ".join([f"{DIMENSIONS[d]} AS `{d}`" for d in dims])
    group_sql = ", ".join([f"`{d}`" for d in dims])
    measure_sql = ", ".join([f"{MEASURES[m]} AS `{m}`" for m in measures])

    sql = f"""
        SELECT {dim_sql}, {measure_sql}
        FROM `tabATM Leads`
        WHERE {" AND ".join(conds)}
        GROUP BY {group_sql}
        ORDER BY {group_sql}
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)

    # Totals across all rows for the same filters
    total_sql = f"SELECT {measure_sql} FROM `tabATM Leads` WHERE {' AND '.join(conds)}"
    totals_row = frappe.db.sql(total_sql, vals, as_dict=True)
    totals = {m: int((totals_row[0] or {}).get(m) or 0) for m in measures}

    return {
        "dimensions": dims,
        "measures": measures,
        "rows": rows,
        "totals": totals,
        "filters": {"start_date": start_date, "end_date": end_date, "company": company, "agent": agent, "state_code": state_code, "status": status},
    }
