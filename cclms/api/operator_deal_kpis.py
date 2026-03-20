import frappe


DATE_FIELD_BY_KPI = {
    "submitted": "submitted_date",
    "approved": "approved_date",
    "rejected": "rejected_date",
    "agreement_sent": "agreement_sent_date",
    "signed": "signed_date",
    "converted": "converted_date",
    "installed": "installed_date",
    "cancelled": "cancelled_date",
    "disputed": "disputed_date",
}


def _existing_operator_deal_fields():
    return set(frappe.get_meta("Operator Deal").get_valid_columns())


def _month_range(month):
    year, month_num = month.split("-")
    year = int(year)
    month_num = int(month_num)
    start = f"{year:04d}-{month_num:02d}-01"
    if month_num == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month_num + 1:02d}-01"
    return start, end


def _deal_filters(operator=None, agent=None):
    filters = []
    params = {}

    if operator:
        filters.append("operator_company = %(operator)s")
        params["operator"] = operator

    if agent:
        filters.append(
            "(sales_agent = %(agent)s OR sales_agent_name_text = %(agent)s OR assigned_agent = %(agent)s)"
        )
        params["agent"] = agent

    return filters, params


@frappe.whitelist()
def monthly_kpis(month, operator=None, agent=None):
    start, end = _month_range(month)
    filters, params = _deal_filters(operator=operator, agent=agent)
    params.update({"start": start, "end": end})

    extra_where = f" AND {' AND '.join(filters)}" if filters else ""
    existing_fields = _existing_operator_deal_fields()

    output = {}
    for kpi, fieldname in DATE_FIELD_BY_KPI.items():
        if fieldname not in existing_fields:
            output[kpi] = 0
            continue
        output[kpi] = frappe.db.sql(
            f"""
            SELECT COUNT(*)
            FROM `tabOperator Deal`
            WHERE {fieldname} >= %(start)s
              AND {fieldname} < %(end)s
              {extra_where}
            """,
            params,
        )[0][0]

    output["net_signed"] = (output.get("signed") or 0) - (output.get("cancelled") or 0)
    return output


@frappe.whitelist()
def trend(kpi, months_back=12, operator=None, agent=None):
    date_field = DATE_FIELD_BY_KPI.get(kpi)
    if not date_field:
        frappe.throw("Invalid KPI")
    if date_field not in _existing_operator_deal_fields():
        return []

    filters, params = _deal_filters(operator=operator, agent=agent)
    filters.append(f"{date_field} IS NOT NULL")
    where = " AND ".join(filters)

    return frappe.db.sql(
        f"""
        SELECT DATE_FORMAT({date_field}, '%%Y-%%m') AS ym, COUNT(*) AS value
        FROM `tabOperator Deal`
        WHERE {where}
        GROUP BY ym
        ORDER BY ym DESC
        LIMIT %(months_back)s
        """,
        {**params, "months_back": int(months_back)},
        as_dict=True,
    )


@frappe.whitelist()
def agent_kpis(month, operator=None):
    start, end = _month_range(month)
    params = {"start": start, "end": end}
    filters = []
    if operator:
        filters.append("operator_company = %(operator)s")
        params["operator"] = operator

    extra_where = f" AND {' AND '.join(filters)}" if filters else ""
    existing_fields = _existing_operator_deal_fields()
    submitted_expr = "SUM(CASE WHEN submitted_date >= %(start)s AND submitted_date < %(end)s THEN 1 ELSE 0 END) AS submitted" if "submitted_date" in existing_fields else "0 AS submitted"
    approved_expr = "SUM(CASE WHEN approved_date >= %(start)s AND approved_date < %(end)s THEN 1 ELSE 0 END) AS approved" if "approved_date" in existing_fields else "0 AS approved"
    agreement_sent_expr = "SUM(CASE WHEN agreement_sent_date >= %(start)s AND agreement_sent_date < %(end)s THEN 1 ELSE 0 END) AS agreement_sent" if "agreement_sent_date" in existing_fields else "0 AS agreement_sent"
    signed_expr = "SUM(CASE WHEN signed_date >= %(start)s AND signed_date < %(end)s THEN 1 ELSE 0 END) AS signed" if "signed_date" in existing_fields else "0 AS signed"
    converted_expr = "SUM(CASE WHEN converted_date >= %(start)s AND converted_date < %(end)s THEN 1 ELSE 0 END) AS converted" if "converted_date" in existing_fields else "0 AS converted"
    installed_expr = "SUM(CASE WHEN installed_date >= %(start)s AND installed_date < %(end)s THEN 1 ELSE 0 END) AS installed" if "installed_date" in existing_fields else "0 AS installed"
    rejected_expr = "SUM(CASE WHEN rejected_date >= %(start)s AND rejected_date < %(end)s THEN 1 ELSE 0 END) AS rejected" if "rejected_date" in existing_fields else "0 AS rejected"
    cancelled_expr = "SUM(CASE WHEN cancelled_date >= %(start)s AND cancelled_date < %(end)s THEN 1 ELSE 0 END) AS cancelled" if "cancelled_date" in existing_fields else "0 AS cancelled"

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(sales_agent, sales_agent_name_text, assigned_agent, 'Unassigned') AS agent,
            {submitted_expr},
            {approved_expr},
            {agreement_sent_expr},
            {signed_expr},
            {converted_expr},
            {installed_expr},
            {rejected_expr},
            {cancelled_expr}
        FROM `tabOperator Deal`
        WHERE 1=1 {extra_where}
        GROUP BY COALESCE(sales_agent, sales_agent_name_text, assigned_agent, 'Unassigned')
        ORDER BY signed DESC, approved DESC
        """,
        params,
        as_dict=True,
    )

    for row in rows:
        row["net_signed"] = (row.get("signed") or 0) - (row.get("cancelled") or 0)

    return rows


@frappe.whitelist()
def signed_list(month, operator=None, agent=None, limit=200):
    start, end = _month_range(month)
    filters, params = _deal_filters(operator=operator, agent=agent)
    params.update({"start": start, "end": end, "limit": int(limit)})
    extra_where = f" AND {' AND '.join(filters)}" if filters else ""
    existing_fields = _existing_operator_deal_fields()
    signed_field = "signed_date" if "signed_date" in existing_fields else None
    if not signed_field:
        return []

    return frappe.db.sql(
        f"""
        SELECT
            name,
            operator_company,
            sales_agent,
            sales_agent_name_text,
            assigned_agent,
            location,
            business_type,
            tier,
            tier_suggestion,
            signed_date,
            agreement_sent_date,
            approved_date
        FROM `tabOperator Deal`
        WHERE signed_date >= %(start)s
          AND signed_date < %(end)s
          {extra_where}
        ORDER BY signed_date DESC
        LIMIT %(limit)s
        """,
        params,
        as_dict=True,
    )
