import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from cclms.api.operator_deal_kpis import DATE_FIELD_BY_KPI, _existing_operator_deal_fields


DEFAULT_TREND_KPIS = ("approved", "agreement_sent", "signed", "installed", "rejected", "cancelled")


def _month_bounds(month_text):
    year, month_num = [int(part) for part in month_text.split("-")]
    start = f"{year:04d}-{month_num:02d}-01"
    if month_num == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month_num + 1:02d}-01"
    return start, end


def _normalize_range(start_date=None, end_date=None, month=None):
    if month:
        return _month_bounds(month)

    today = getdate(nowdate())
    if not start_date:
        start_date = today.replace(day=1)
    if not end_date:
        end_date = today
    return str(getdate(start_date)), str(getdate(end_date))


def _deal_filters(operator=None, agent=None):
    clauses = []
    params = {}
    if operator:
        clauses.append("operator_company = %(operator)s")
        params["operator"] = operator
    if agent:
        clauses.append("(sales_agent = %(agent)s OR sales_agent_name_text = %(agent)s OR assigned_agent = %(agent)s)")
        params["agent"] = agent
    return clauses, params


def _count_between(fieldname, start_date, end_date_exclusive, clauses, params):
    existing_fields = _existing_operator_deal_fields()
    if fieldname not in existing_fields:
        return 0

    extra_where = f" AND {' AND '.join(clauses)}" if clauses else ""
    return frappe.db.sql(
        f"""
        SELECT COUNT(*)
        FROM `tabOperator Deal`
        WHERE {fieldname} >= %(start)s
          AND {fieldname} < %(end)s
          {extra_where}
        """,
        {**params, "start": start_date, "end": end_date_exclusive},
    )[0][0]


def _normalize_number_fields(rows, fieldnames):
    for row in rows:
        for fieldname in fieldnames:
            if fieldname in row and row.get(fieldname) is not None:
                row[fieldname] = int(row.get(fieldname) or 0)
    return rows


@frappe.whitelist()
def overview(start_date=None, end_date=None, month=None, operator=None, agent=None):
    start_date, end_date = _normalize_range(start_date=start_date, end_date=end_date, month=month)
    end_exclusive = frappe.utils.add_days(getdate(end_date), 1)
    clauses, params = _deal_filters(operator=operator, agent=agent)

    counts = {}
    for key, fieldname in DATE_FIELD_BY_KPI.items():
        counts[key] = _count_between(fieldname, start_date, end_exclusive, clauses, params)
    counts["net_signed"] = (counts.get("signed") or 0) - (counts.get("cancelled") or 0)

    status_extra_where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    status_rows = frappe.db.sql(
        f"""
        SELECT COALESCE(status, 'Unknown') AS label, COUNT(*) AS value
        FROM `tabOperator Deal`
        {status_extra_where}
        GROUP BY COALESCE(status, 'Unknown')
        ORDER BY value DESC, label ASC
        """,
        params,
        as_dict=True,
    )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "counts": counts,
        "status_snapshot": status_rows,
    }


@frappe.whitelist()
def company_breakdown(start_date=None, end_date=None, month=None, operator=None, agent=None):
    start_date, end_date = _normalize_range(start_date=start_date, end_date=end_date, month=month)
    end_exclusive = frappe.utils.add_days(getdate(end_date), 1)
    clauses, params = _deal_filters(operator=operator, agent=agent)
    extra_where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    fields = _existing_operator_deal_fields()

    def event_sum(fieldname, alias):
        if fieldname not in fields:
            return f"0 AS {alias}"
        return (
            f"SUM(CASE WHEN {fieldname} >= %(start)s AND {fieldname} < %(end)s THEN 1 ELSE 0 END) AS {alias}"
        )

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(operator_company, 'Unknown') AS operator_company,
            {event_sum('submitted_date', 'submitted')},
            {event_sum('approved_date', 'approved')},
            {event_sum('agreement_sent_date', 'agreement_sent')},
            {event_sum('signed_date', 'signed')},
            {event_sum('converted_date', 'converted')},
            {event_sum('installed_date', 'installed')},
            {event_sum('rejected_date', 'rejected')},
            {event_sum('cancelled_date', 'cancelled')},
            COUNT(*) AS total_deals
        FROM `tabOperator Deal`
        {extra_where}
        GROUP BY COALESCE(operator_company, 'Unknown')
        ORDER BY signed DESC, approved DESC, operator_company ASC
        """,
        {**params, "start": start_date, "end": end_exclusive},
        as_dict=True,
    )

    for row in rows:
        row["net_signed"] = (row.get("signed") or 0) - (row.get("cancelled") or 0)
    return _normalize_number_fields(
        rows,
        ["submitted", "approved", "agreement_sent", "signed", "converted", "installed", "rejected", "cancelled", "total_deals", "net_signed"],
    )


@frappe.whitelist()
def agent_breakdown(start_date=None, end_date=None, month=None, operator=None):
    start_date, end_date = _normalize_range(start_date=start_date, end_date=end_date, month=month)
    end_exclusive = frappe.utils.add_days(getdate(end_date), 1)
    clauses, params = _deal_filters(operator=operator)
    extra_where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    fields = _existing_operator_deal_fields()
    agent_expr = "COALESCE(sales_agent, sales_agent_name_text, assigned_agent, 'Unassigned')"

    def event_sum(fieldname, alias):
        if fieldname not in fields:
            return f"0 AS {alias}"
        return (
            f"SUM(CASE WHEN {fieldname} >= %(start)s AND {fieldname} < %(end)s THEN 1 ELSE 0 END) AS {alias}"
        )

    rows = frappe.db.sql(
        f"""
        SELECT
            {agent_expr} AS agent,
            {event_sum('submitted_date', 'submitted')},
            {event_sum('approved_date', 'approved')},
            {event_sum('agreement_sent_date', 'agreement_sent')},
            {event_sum('signed_date', 'signed')},
            {event_sum('converted_date', 'converted')},
            {event_sum('installed_date', 'installed')},
            {event_sum('rejected_date', 'rejected')},
            {event_sum('cancelled_date', 'cancelled')},
            COUNT(*) AS total_deals
        FROM `tabOperator Deal`
        {extra_where}
        GROUP BY {agent_expr}
        ORDER BY signed DESC, approved DESC, agent ASC
        """,
        {**params, "start": start_date, "end": end_exclusive},
        as_dict=True,
    )

    for row in rows:
        row["net_signed"] = (row.get("signed") or 0) - (row.get("cancelled") or 0)
    normalized = _normalize_number_fields(
        rows,
        ["submitted", "approved", "agreement_sent", "signed", "converted", "installed", "rejected", "cancelled", "total_deals", "net_signed"],
    )

    # Fallback: when there are no Operator Deal records (e.g. deal doctype unused),
    # aggregate ATM Leads by Sales Agent (executive_name) so the Agents page is wired.
    if not normalized:
        normalized = _agent_breakdown_from_atm_leads(start_date, end_date, operator)
    return normalized


def _agent_breakdown_from_atm_leads(start_date, end_date, operator=None):
    conds, vals = [], []
    if operator:
        conds.append("company = %s"); vals.append(operator)
    if start_date and end_date:
        conds.append("creation >= %s AND creation < %s")
        vals.extend([start_date, frappe.utils.add_days(getdate(end_date), 1)])
    where_sql = f"WHERE {' AND '.join(conds)}" if conds else ""
    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(executive_name, ''), 'Unassigned') AS agent,
            SUM(CASE WHEN workflow_state = 'Approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN workflow_state = 'Agreement Sent' THEN 1 ELSE 0 END) AS agreement_sent,
            SUM(CASE WHEN workflow_state = 'Signed' THEN 1 ELSE 0 END) AS signed,
            SUM(CASE WHEN workflow_state = 'Converted' THEN 1 ELSE 0 END) AS converted,
            SUM(CASE WHEN workflow_state = 'Installed' THEN 1 ELSE 0 END) AS installed,
            SUM(CASE WHEN workflow_state = 'Rejected' THEN 1 ELSE 0 END) AS rejected,
            COUNT(*) AS total_deals
        FROM `tabATM Leads`
        {where_sql}
        GROUP BY agent
        ORDER BY signed DESC, approved DESC, agent ASC
        """,
        vals,
        as_dict=True,
    )
    for row in rows:
        row["net_signed"] = (row.get("signed") or 0) - (row.get("cancelled") or 0)
        row.setdefault("submitted", 0)
        row.setdefault("cancelled", 0)
    return rows


@frappe.whitelist()
def multi_trend(months_back=12, operator=None, agent=None):
    fields = _existing_operator_deal_fields()
    clauses, params = _deal_filters(operator=operator, agent=agent)
    series_maps = {}
    month_labels = set()

    for kpi in DEFAULT_TREND_KPIS:
        fieldname = DATE_FIELD_BY_KPI.get(kpi)
        if not fieldname or fieldname not in fields:
            series_maps[kpi] = {}
            continue

        local_clauses = list(clauses) + [f"{fieldname} IS NOT NULL"]
        where_sql = " AND ".join(local_clauses)
        rows = frappe.db.sql(
            f"""
            SELECT DATE_FORMAT({fieldname}, '%%Y-%%m') AS ym, COUNT(*) AS value
            FROM `tabOperator Deal`
            WHERE {where_sql}
            GROUP BY ym
            ORDER BY ym DESC
            LIMIT %(months_back)s
            """,
            {**params, "months_back": int(months_back)},
            as_dict=True,
        )
        data_map = {row.ym: int(row.value) for row in rows}
        series_maps[kpi] = data_map
        month_labels.update(data_map.keys())

    months = sorted(month_labels)
    series = []
    for kpi in DEFAULT_TREND_KPIS:
        series.append(
            {
                "name": kpi.replace("_", " ").title(),
                "key": kpi,
                "data": [series_maps.get(kpi, {}).get(month, 0) for month in months],
            }
        )

    return {"categories": months, "series": series}


@frappe.whitelist()
def recent_signed(start_date=None, end_date=None, month=None, operator=None, agent=None, limit=20):
    start_date, end_date = _normalize_range(start_date=start_date, end_date=end_date, month=month)
    end_exclusive = frappe.utils.add_days(getdate(end_date), 1)
    clauses, params = _deal_filters(operator=operator, agent=agent)
    clauses.insert(0, "signed_date >= %(start)s")
    clauses.insert(1, "signed_date < %(end)s")
    where_sql = " AND ".join(clauses)

    return frappe.db.sql(
        f"""
        SELECT
            name,
            operator_company,
            location,
            business_type,
            sales_agent,
            sales_agent_name_text,
            assigned_agent,
            tier,
            tier_suggestion,
            signed_date,
            approved_date,
            installed_date
        FROM `tabOperator Deal`
        WHERE {where_sql}
        ORDER BY signed_date DESC
        LIMIT %(limit)s
        """,
        {**params, "start": start_date, "end": end_exclusive, "limit": int(limit)},
        as_dict=True,
    )


@frappe.whitelist()
def zip_analytics_overview():
    if not frappe.db.exists("DocType", "Zip Code Analytics"):
        return {"zones": [], "totals": {}}

    zones = frappe.db.sql(
        """
        SELECT
            COALESCE(zone_color, 'Unknown') AS zone,
            COUNT(*) AS total,
            ROUND(AVG(IFNULL(zip_score, 0)), 2) AS avg_zip_score,
            ROUND(AVG(IFNULL(competitor_density, 0)), 2) AS avg_competitor_density,
            ROUND(AVG(IFNULL(population_density, 0)), 2) AS avg_population_density
        FROM `tabZip Code Analytics`
        GROUP BY COALESCE(zone_color, 'Unknown')
        ORDER BY total DESC
        """,
        as_dict=True,
    )

    totals = frappe.db.sql(
        """
        SELECT
            COUNT(*) AS total_zips,
            SUM(CASE WHEN COALESCE(zone_color, '') IN ('Green', 'Light Green', 'Yellow') THEN 1 ELSE 0 END) AS actionable_zips,
            SUM(CASE WHEN IFNULL(competitor_kiosks, 0) > 0 THEN 1 ELSE 0 END) AS zips_with_competitors,
            SUM(CASE WHEN IFNULL(company_kiosks, 0) > 0 THEN 1 ELSE 0 END) AS zips_with_our_kiosks
        FROM `tabZip Code Analytics`
        """,
        as_dict=True,
    )[0]

    return {"zones": zones, "totals": totals}
