import frappe

# Ordered pipeline columns for the pivot (matches ATM Leads workflow states)
PIPELINE = [
    "Submitted", "Pending", "Approved", "Agreement Sent", "Pending Sign",
    "Signed", "Converted", "Installed", "Rejected", "Signed Rejected",
    "Not Qualified", "Cancelled", "Not Interested", "Interested",
]

WORKFLOW_STATES = {
    "Submitted": ["Submitted"],
    "Pending": ["Pending"],
    "Approved": ["Approved"],
    "Agreement Sent": ["Agreement Sent", "Requested for Agreement Sent"],
    "Pending Sign": ["Pending Sign"],
    "Signed": ["Signed"],
    "Converted": ["Converted"],
    "Installed": ["Installed"],
    "Rejected": ["Rejected"],
    "Signed Rejected": ["Signed Rejected"],
    "Not Qualified": ["Not Qualified"],
    "Cancelled": ["Cancelled"],
    "Not Interested": ["Not Interested"],
    "Interested": ["Interested"],
}

# stage -> date field (measures transitions within the window)
DATE_FIELDS = {
    "Submitted": "post_date",
    "Pending": "submitted_date",
    "Approved": "approve_date",
    "Agreement Sent": "agreement_sent_date",
    "Signed": "sign_date",
    "Converted": "convert_date",
    "Installed": "install_date",
    "Rejected": "rejected_date",
    "Cancelled": "cancelled_date",
}


def _safe_col(df):
    return df if frappe.db.has_column("ATM Leads", df) else None


@frappe.whitelist(allow_guest=True)
def workflow_pivot(start_date=None, end_date=None, company=None, agent=None):
    """Company x Sales Agent x workflow-stage pivot table.

    One row per (company, agent); each workflow stage is a column with a count
    (measured by the stage's own date field when available, else live state).
    """
    from frappe.utils import getdate, add_days
    start = start_date or str(getdate().replace(day=1))
    end = end_date or str(getdate())
    end_excl = str(add_days(getdate(end), 1))

    conds, params = ["docstatus < 2"], {"start": start, "end": end_excl}
    if company:
        conds.append("company = %(company)s"); params["company"] = company
    if agent:
        conds.append("executive_name = %(agent)s"); params["agent"] = agent

    # Build stage columns
    select_cols = []
    for stage in PIPELINE:
        f = DATE_FIELDS.get(stage)
        if f and _safe_col(f):
            select_cols.append(
                f"SUM(CASE WHEN `{f}` IS NOT NULL AND `{f}` >= %(start)s AND `{f}` < %(end)s THEN 1 ELSE 0 END) AS `{stage}`"
            )
        else:
            states = WORKFLOW_STATES.get(stage, [stage])
            expr = " + ".join([f"(CASE WHEN IFNULL(workflow_state,'')='{s}' THEN 1 ELSE 0 END)" for s in states])
            select_cols.append(f"SUM({expr}) AS `{stage}`")

    where = " AND ".join(conds)
    sql = f"""
        SELECT
            COALESCE(NULLIF(company,''),'—') AS company,
            COALESCE(NULLIF(executive_name,''),'Unassigned') AS agent,
            {", ".join(select_cols)},
            COUNT(name) AS total
        FROM `tabATM Leads`
        WHERE {where}
        GROUP BY company, agent
        ORDER BY company ASC, agent ASC
    """
    rows = frappe.db.sql(sql, params, as_dict=True)

    total_sql = f"""
        SELECT {", ".join(select_cols)}, COUNT(name) AS total
        FROM `tabATM Leads` WHERE {where}
    """
    totals_row = frappe.db.sql(total_sql, params, as_dict=True)[0]
    totals = {}
    for k, v in (totals_row or {}).items():
        if k not in ("company", "agent"):
            totals[k] = int(v or 0)

    normalized = []
    for r in rows:
        row = {"company": r.get("company") or "—", "agent": r.get("agent") or "Unassigned"}
        for k, v in r.items():
            if k not in ("company", "agent"):
                row[k] = int(v or 0)
        row["total"] = row.get("total") or sum(row.get(s, 0) for s in PIPELINE)
        normalized.append(row)

    return {
        "dimensions": ["company", "agent"],
        "stages": PIPELINE,
        "rows": normalized,
        "totals": totals,
        "filters": {"start_date": start, "end_date": end, "company": company, "agent": agent},
    }
