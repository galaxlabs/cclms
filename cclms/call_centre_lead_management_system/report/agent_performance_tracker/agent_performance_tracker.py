from datetime import date

import frappe


def _month_window(filters):
    month = (filters or {}).get("month")
    if month:
        year, month_no = [int(part) for part in str(month).split("-")[:2]]
        start = date(year, month_no, 1)
    else:
        today = date.today()
        start = today.replace(day=1)

    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    return start, end


def execute(filters=None):
    filters = filters or {}
    start, end = _month_window(filters)

    call_map = {
        row.employee: row
        for row in frappe.db.sql(
            """
            SELECT employee,
                   SUM(total_calls) AS total_calls,
                   SUM(total_talk_time_seconds) AS total_talk_time_seconds
            FROM `tabCall Daily Summary`
            WHERE date >= %(start)s AND date < %(end)s
            GROUP BY employee
            """,
            {"start": str(start), "end": str(end)},
            as_dict=True,
        )
    }

    activity_map = {
        row.employee: row
        for row in frappe.db.sql(
            """
            SELECT employee,
                   COUNT(*) AS attendance_days,
                   SUM(total_active_minutes) AS total_active_minutes,
                   SUM(total_idle_minutes) AS total_idle_minutes,
                   SUM(unauthorized_site_hits) AS unauthorized_site_hits
            FROM `tabEmployee Activity Log`
            WHERE date >= %(start)s AND date < %(end)s
              AND IFNULL(employee, '') != ''
            GROUP BY employee
            """,
            {"start": str(start), "end": str(end)},
            as_dict=True,
        )
    }

    deal_rows = frappe.db.sql(
        """
        SELECT
            COALESCE(sa.agent_name, od.sales_agent_name_text, emp.employee_name, usr.full_name, od.assigned_agent, 'Unassigned') AS agent_label,
            emp.name AS employee,
            od.sales_agent,
            od.assigned_agent,
            SUM(CASE WHEN od.signed_date >= %(start)s AND od.signed_date < %(end)s THEN 1 ELSE 0 END) AS signed_count,
            SUM(CASE WHEN od.installed_date >= %(start)s AND od.installed_date < %(end)s THEN 1 ELSE 0 END) AS installed_count,
            SUM(CASE WHEN od.approved_date >= %(start)s AND od.approved_date < %(end)s THEN 1 ELSE 0 END) AS approved_count,
            SUM(CASE WHEN od.agreement_sent_date >= %(start)s AND od.agreement_sent_date < %(end)s THEN 1 ELSE 0 END) AS agreement_sent_count,
            SUM(CASE WHEN od.cancelled_date >= %(start)s AND od.cancelled_date < %(end)s THEN 1 ELSE 0 END) AS cancelled_count
        FROM `tabOperator Deal` od
        LEFT JOIN `tabSales Agent` sa ON sa.name = od.sales_agent
        LEFT JOIN `tabUser` usr ON usr.name = od.assigned_agent
        LEFT JOIN `tabEmployee` emp ON emp.user_id = od.assigned_agent
        GROUP BY agent_label, employee, od.sales_agent, od.assigned_agent
        ORDER BY signed_count DESC, installed_count DESC, approved_count DESC, agent_label ASC
        """,
        {"start": str(start), "end": str(end)},
        as_dict=True,
    )

    columns = [
        {"label": "Agent", "fieldname": "agent", "fieldtype": "Data", "width": 220},
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 160},
        {"label": "Approved", "fieldname": "approved_count", "fieldtype": "Int", "width": 90},
        {"label": "Agreement Sent", "fieldname": "agreement_sent_count", "fieldtype": "Int", "width": 120},
        {"label": "Signed", "fieldname": "signed_count", "fieldtype": "Int", "width": 90},
        {"label": "Installed", "fieldname": "installed_count", "fieldtype": "Int", "width": 90},
        {"label": "Cancelled", "fieldname": "cancelled_count", "fieldtype": "Int", "width": 90},
        {"label": "Calls", "fieldname": "total_calls", "fieldtype": "Int", "width": 90},
        {"label": "Talk Sec", "fieldname": "total_talk_time_seconds", "fieldtype": "Int", "width": 100},
        {"label": "Attendance Days", "fieldname": "attendance_days", "fieldtype": "Int", "width": 120},
        {"label": "Active Min", "fieldname": "total_active_minutes", "fieldtype": "Float", "width": 100},
        {"label": "Idle Min", "fieldname": "total_idle_minutes", "fieldtype": "Float", "width": 100},
        {"label": "Unauthorized Sites", "fieldname": "unauthorized_site_hits", "fieldtype": "Int", "width": 130}
    ]

    data = []
    for row in deal_rows:
        activity = activity_map.get(row.employee) if row.employee else None
        calls = call_map.get(row.employee) if row.employee else None
        data.append(
            {
                "agent": row.agent_label,
                "employee": row.employee,
                "approved_count": int(row.approved_count or 0),
                "agreement_sent_count": int(row.agreement_sent_count or 0),
                "signed_count": int(row.signed_count or 0),
                "installed_count": int(row.installed_count or 0),
                "cancelled_count": int(row.cancelled_count or 0),
                "total_calls": int((calls.total_calls if calls else 0) or 0),
                "total_talk_time_seconds": int((calls.total_talk_time_seconds if calls else 0) or 0),
                "attendance_days": int((activity.attendance_days if activity else 0) or 0),
                "total_active_minutes": float((activity.total_active_minutes if activity else 0) or 0),
                "total_idle_minutes": float((activity.total_idle_minutes if activity else 0) or 0),
                "unauthorized_site_hits": int((activity.unauthorized_site_hits if activity else 0) or 0),
            }
        )

    chart = {
        "data": {
            "labels": [row["agent"] for row in data[:12]],
            "datasets": [
                {"name": "Signed", "values": [row["signed_count"] for row in data[:12]]},
                {"name": "Installed", "values": [row["installed_count"] for row in data[:12]]},
            ],
        },
        "type": "bar",
        "colors": ["#0f766e", "#2563eb"],
    }

    report_summary = [
        {"label": "Month Start", "value": str(start), "datatype": "Data"},
        {"label": "Month End", "value": str(end), "datatype": "Data"},
        {"label": "Signed", "value": sum(row["signed_count"] for row in data), "datatype": "Int"},
        {"label": "Installed", "value": sum(row["installed_count"] for row in data), "datatype": "Int"},
        {"label": "Calls", "value": sum(row["total_calls"] for row in data), "datatype": "Int"},
    ]

    return columns, data, None, chart, report_summary

