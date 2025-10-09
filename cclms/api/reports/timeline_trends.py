import frappe

def _safe_col(df: str) -> str:
    return df if frappe.db.has_column("ATM Leads", df) else "creation"

def _where(parts):
    return "WHERE " + " AND ".join(parts) if parts else ""

def _series_for(col, start_date, end_date, company, executive_name):
    conds, vals = [], []
    if start_date and end_date:
        conds.append(f"{col} BETWEEN %s AND %s"); vals.extend([start_date, end_date])
    if company:
        conds.append("company = %s"); vals.append(company)
    if executive_name:
        conds.append("executive_name = %s"); vals.append(executive_name)
    conds.append("IFNULL(workflow_state,'') <> 'Draft'")  # defensive

    sql = f"""
      SELECT DATE_FORMAT({col}, '%%Y-%%m') AS bucket, COUNT(name) AS total
      FROM `tabATM Leads`
      {_where(conds)}
      GROUP BY bucket
      ORDER BY bucket
    """
    return frappe.db.sql(sql, values=vals, as_dict=True)

@frappe.whitelist(allow_guest=True)
def get_multi_trends(
    start_date=None, end_date=None, company=None, executive_name=None,
    approve_date_field="approve_date",
    sent_date_field="agreement_sent_date",
    sign_date_field="sign_date",
    convert_date_field="convert_date"
):
    appr = _safe_col(approve_date_field)
    sent = _safe_col(sent_date_field)
    sign = _safe_col(sign_date_field)
    conv = _safe_col(convert_date_field)

    s1 = _series_for(appr, start_date, end_date, company, executive_name)
    s2 = _series_for(sent, start_date, end_date, company, executive_name)
    s3 = _series_for(sign, start_date, end_date, company, executive_name)
    s4 = _series_for(conv, start_date, end_date, company, executive_name)

    # union buckets
    months = sorted(set([r.bucket for r in (s1+s2+s3+s4)]))
    def to_map(rows): return {r.bucket: int(r.total) for r in rows}
    m1, m2, m3, m4 = map(to_map, [s1, s2, s3, s4])

    return {
        "categories": months,
        "series": [
            {"name": "Approved",        "data": [m1.get(m, 0) for m in months]},
            {"name": "Agreement Sent",  "data": [m2.get(m, 0) for m in months]},
            {"name": "Signed",          "data": [m3.get(m, 0) for m in months]},
            {"name": "Converted",       "data": [m4.get(m, 0) for m in months]},
        ]
    }
