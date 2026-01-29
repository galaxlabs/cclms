import frappe
from frappe.utils import getdate

DATE_FIELD_BY_KPI = {
    "approved": "approved_date",
    "rejected": "rejected_date",
    "agreement_sent": "agreement_sent_date",
    "signed": "signed_date",
    "converted": "converted_date",
    "installed": "installed_date",
    "cancelled": "cancelled_date",
}

def _month_range(month: str):
    # month format: 'YYYY-MM'
    start = f"{month}-01"
    y, m = month.split("-")
    y = int(y); m = int(m)
    if m == 12:
        end = f"{y+1}-01-01"
    else:
        end = f"{y}-{m+1:02d}-01"
    return start, end

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

    out["net_signed"] = (out["signed"] or 0) - (out["cancelled"] or 0)
    return out

@frappe.whitelist()
def trend(kpi: str, months_back: int = 12, operator: str | None = None, agent: str | None = None):
    df = DATE_FIELD_BY_KPI.get(kpi)
    if not df:
        frappe.throw("Invalid KPI")

    filters = ["{df} IS NOT NULL".format(df=df)]
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
