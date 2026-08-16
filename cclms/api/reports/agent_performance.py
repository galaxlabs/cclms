import frappe

def _safe_date_field(df: str) -> str:
    return df if frappe.db.has_column("ATM Leads", df) else "creation"

def _norm(v):
    return int(v or 0)

@frappe.whitelist(allow_guest=True)
def get_agent_performance(state="Signed", start_date=None, end_date=None, from_date=None, to_date=None, company=None, date_field="sign_date"):
    """Agent performance metrics from ATM Leads, grouped by executive (sales agent).

    Returns one row per agent with total_leads, approved, signed, rejected, converted,
    installed, sign_rate, approval_rate, and avg_response_days. Supports the frontend's
    from_date/to_date params in addition to start_date/end_date.
    """
    sd = from_date or start_date
    ed = to_date or end_date
    df = _safe_date_field(date_field)

    conds, vals = [], []
    if company:
        conds.append("company = %s"); vals.append(company)
    if sd and ed:
        conds.append(f"COALESCE({df}, creation) BETWEEN %s AND %s")
        vals.extend([sd, ed])

    where_sql = "WHERE " + " AND ".join(conds) if conds else ""
    sql = f"""
        SELECT
            COALESCE(NULLIF(executive_name, ''), 'Unassigned') AS agent,
            COUNT(*) AS total_leads,
            SUM(CASE WHEN workflow_state = 'Approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN workflow_state = 'Signed' THEN 1 ELSE 0 END) AS signed,
            SUM(CASE WHEN workflow_state = 'Rejected' THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN workflow_state = 'Converted' THEN 1 ELSE 0 END) AS converted,
            SUM(CASE WHEN workflow_state = 'Installed' THEN 1 ELSE 0 END) AS installed,
            AVG(CASE WHEN {df} IS NOT NULL
                THEN GREATEST(TIMESTAMPDIFF(DAY, creation, {df}), 0) END) AS avg_response_days
        FROM `tabATM Leads`
        {where_sql}
        GROUP BY agent
        ORDER BY signed DESC, approved DESC, total_leads DESC
    """
    rows = frappe.db.sql(sql, values=vals, as_dict=True)

    out = []
    for r in rows:
        total = _norm(r.get("total_leads"))
        signed = _norm(r.get("signed"))
        approved = _norm(r.get("approved"))
        rejected = _norm(r.get("rejected"))
        converted = _norm(r.get("converted"))
        installed = _norm(r.get("installed"))
        # Only include agents that actually have records in this window
        if total == 0 and signed == 0 and approved == 0 and rejected == 0:
            continue
        out.append({
            "agent_name": r.get("agent") or "Unassigned",
            "executive_name": r.get("agent"),
            "total_leads": total,
            "approved": approved,
            "signed": signed,
            "rejected": rejected,
            "converted": converted,
            "installed": installed,
            "sign_rate": round(signed / total * 100, 1) if total else 0,
            "approval_rate": round(approved / total * 100, 1) if total else 0,
            "avg_response_days": round(float(r.get("avg_response_days") or 0), 1),
        })
    return out
