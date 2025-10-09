import frappe

def _safe_col(df: str) -> str:
    return df if frappe.db.has_column("ATM Leads", df) else "creation"

def _where(parts):
    return "WHERE " + " AND ".join(parts) if parts else ""

@frappe.whitelist(allow_guest=True)
def get_executive_overview(
    start_date=None, end_date=None, company=None,
    post_date_field="post_date",
    approve_date_field="approve_date",
    sent_date_field="agreement_sent_date",
    sign_date_field="sign_date",
    convert_date_field="convert_date"
):
    post = _safe_col(post_date_field)
    appr = _safe_col(approve_date_field)
    sent = _safe_col(sent_date_field)
    sign = _safe_col(sign_date_field)
    conv = _safe_col(convert_date_field)

    # total by post_date (only those with >=1)
    base_conds, base_vals = [], []
    if start_date and end_date:
        base_conds.append(f"{post} BETWEEN %s AND %s"); base_vals.extend([start_date, end_date])
    if company:
        base_conds.append("company = %s"); base_vals.append(company)
    base_conds.append("IFNULL(workflow_state,'') <> 'Draft'")

    totals = frappe.db.sql(f"""
      SELECT executive_name, COUNT(name) AS total_post
      FROM `tabATM Leads`
      {_where(base_conds)}
      GROUP BY executive_name
      HAVING total_post > 0
      ORDER BY total_post DESC
    """, values=base_vals, as_dict=True)

    # helper: count per executive for an event col within window
    def per_exec(col):
        c, v = [], []
        if start_date and end_date:
            c.append(f"{col} BETWEEN %s AND %s"); v.extend([start_date, end_date])
        if company:
            c.append("company = %s"); v.append(company)
        c.append("IFNULL(workflow_state,'') <> 'Draft'")
        rows = frappe.db.sql(f"""
            SELECT executive_name, COUNT(name) AS cnt
            FROM `tabATM Leads`
            {_where(c)}
            GROUP BY executive_name
        """, values=v, as_dict=True)
        return {r.executive_name: int(r.cnt) for r in rows}

    m_appr = per_exec(appr)
    m_sent = per_exec(sent)
    m_sign = per_exec(sign)
    m_conv = per_exec(conv)

    out = []
    for row in totals:
        exe = row.executive_name or "-"
        t = int(row.total_post)
        a = m_appr.get(exe, 0)
        s = m_sent.get(exe, 0)
        sg = m_sign.get(exe, 0)
        cv = m_conv.get(exe, 0)
        out.append({
            "executive_name": exe,
            "total_post": t,
            "approved": a,
            "agreement_sent": s,
            "signed": sg,
            "converted": cv,
            "signed_plus_converted": sg + cv,
        })
    return {"rows": out}
