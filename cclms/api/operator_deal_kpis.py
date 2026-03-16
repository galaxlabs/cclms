import frappe

# -------------------------
# Helpers
# -------------------------

def _month_range(month: str):
    """
    month: 'YYYY-MM'
    returns (start_date_str, end_date_str) in 'YYYY-MM-DD'
    """
    y, m = month.split("-")
    y = int(y)
    m = int(m)

    start = f"{y:04d}-{m:02d}-01"

    if m == 12:
        end = f"{y+1:04d}-01-01"
    else:
        end = f"{y:04d}-{m+1:02d}-01"

    return start, end


DATE_FIELD_BY_KPI = {
    "approved": "approved_date",
    "rejected": "rejected_date",
    "agreement_sent": "agreement_sent_date",
    "signed": "signed_date",
    "converted": "converted_date",
    "installed": "installed_date",
    "cancelled": "cancelled_date",
}

# -------------------------
# KPI cards (month totals)
# -------------------------

@frappe.whitelist()
def monthly_kpis(month: str, operator: str | None = None, agent: str | None = None):
    start, end = _month_range(month)

    base_filters = []
    params = {"start": start, "end": end}

    if operator:
        base_filters.append("operator_company = %(operator)s")
        params["operator"] = operator

    if agent:
        base_filters.append("assigned_agent = %(agent)s")
        params["agent"] = agent

    base_where = (" AND " + " AND ".join(base_filters)) if base_filters else ""

    out = {}
    for kpi, df in DATE_FIELD_BY_KPI.items():
        out[kpi] = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabOperator Deal`
            WHERE {df} >= %(start)s AND {df} < %(end)s
            {base_where}
        """, params)[0][0]

    out["net_signed"] = (out.get("signed") or 0) - (out.get("cancelled") or 0)
    return out

# -------------------------
# Trend line (ECharts)
# -------------------------

@frappe.whitelist()
def trend(kpi: str, months_back: int = 12, operator: str | None = None, agent: str | None = None):
    df = DATE_FIELD_BY_KPI.get(kpi)
    if not df:
        frappe.throw("Invalid KPI")

    filters = [f"{df} IS NOT NULL"]
    params = {}

    if operator:
        filters.append("operator_company = %(operator)s")
        params["operator"] = operator

    if agent:
        filters.append("assigned_agent = %(agent)s")
        params["agent"] = agent

    where = " AND ".join(filters)

    return frappe.db.sql(f"""
        SELECT DATE_FORMAT({df}, '%%Y-%%m') AS ym, COUNT(*) AS value
        FROM `tabOperator Deal`
        WHERE {where}
        GROUP BY ym
        ORDER BY ym DESC
        LIMIT {int(months_back)}
    """, params, as_dict=True)

# -------------------------
# Agent KPI table (month)
# -------------------------

@frappe.whitelist()
def agent_kpis(month: str, operator: str | None = None):
    start, end = _month_range(month)

    params = {"start": start, "end": end}
    cond = ""
    if operator:
        cond = " AND operator_company = %(operator)s"
        params["operator"] = operator

    rows = frappe.db.sql(f"""
        SELECT
            assigned_agent AS agent,
            SUM(CASE WHEN submitted_date >= %(start)s AND submitted_date < %(end)s THEN 1 ELSE 0 END) AS posted,
            SUM(CASE WHEN approved_date >= %(start)s AND approved_date < %(end)s THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN agreement_sent_date >= %(start)s AND agreement_sent_date < %(end)s THEN 1 ELSE 0 END) AS agreement_sent,
            SUM(CASE WHEN signed_date >= %(start)s AND signed_date < %(end)s THEN 1 ELSE 0 END) AS signed,
            SUM(CASE WHEN converted_date >= %(start)s AND converted_date < %(end)s THEN 1 ELSE 0 END) AS converted,
            SUM(CASE WHEN installed_date >= %(start)s AND installed_date < %(end)s THEN 1 ELSE 0 END) AS installed,
            SUM(CASE WHEN rejected_date >= %(start)s AND rejected_date < %(end)s THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN cancelled_date >= %(start)s AND cancelled_date < %(end)s THEN 1 ELSE 0 END) AS cancelled
        FROM `tabOperator Deal`
        WHERE 1=1 {cond}
        GROUP BY assigned_agent
        ORDER BY signed DESC
    """, params, as_dict=True)

    for r in rows:
        r["net_signed"] = (r.get("signed") or 0) - (r.get("cancelled") or 0)

    return rows

# -------------------------
# Signed drill-down list
# -------------------------

@frappe.whitelist()
def signed_list(month: str, operator: str | None = None, agent: str | None = None, limit: int = 200):
    start, end = _month_range(month)

    params = {"start": start, "end": end, "limit": int(limit)}
    cond = []
    if operator:
        cond.append("operator_company = %(operator)s")
        params["operator"] = operator
    if agent:
        cond.append("assigned_agent = %(agent)s")
        params["agent"] = agent

    extra_where = (" AND " + " AND ".join(cond)) if cond else ""

    return frappe.db.sql(f"""
        SELECT
            name,
            operator_company,
            assigned_agent,
            location,
            business_type,
            tier,
            signed_date,
            agreement_sent_date,
            approved_date
        FROM `tabOperator Deal`
        WHERE signed_date >= %(start)s AND signed_date < %(end)s
        {extra_where}
        ORDER BY signed_date DESC
        LIMIT %(limit)s
    """, params, as_dict=True)
