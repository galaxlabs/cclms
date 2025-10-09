# Copyright (c) 2025, Galaxy and contributors
# For license information, please see license.txt

import frappe
from datetime import date, datetime
from calendar import monthrange
from typing import List, Tuple, Dict, Any, Optional


# ---------- Utility Functions ----------
def _parse_date(s: Optional[str]) -> Optional[date]:
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None

def _month_start(d: date) -> date:
    return d.replace(day=1)

def _month_end(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])

def _iter_months(from_dt: date, to_dt: date) -> List[Tuple[str, date, date]]:
    out = []
    cur = _month_start(from_dt)
    while cur <= to_dt:
        out.append((f"{cur.year}-{cur.month:02d}", cur, _month_end(cur)))
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return out

def _pct(n, d):
    return round((n / d) * 100, 2) if d else 0.0


# ---------- Main ----------
def execute(filters: Optional[Dict[str, Any]] = None):
    """
    Executive Performance (Monthly)
    - Groups by Sales Agent (executive_name) per month
    - Counts all major workflow stages + conversion ratios + rejection %
    - Based only on post_date range
    """
    filters = filters or {}
    today = date.today()
    from_date = _parse_date(filters.get("from_date")) or date(today.year, 1, 1)
    to_date = _parse_date(filters.get("to_date")) or today
    company = filters.get("company")
    branch = filters.get("branch")

    # --- Field mapping ---
    post_f = "post_date"
    appr_f = "approve_date"
    sent_f = "agreement_sent_date"
    sign_f = "sign_date"
    conv_f = "convert_date"
    inst_f = "install_date"

    # --- Base WHERE ---
    where = ["IFNULL(workflow_state,'') <> 'Draft'", "docstatus < 2"]
    vals: List[Any] = []
    if company:
        where.append("company = %s"); vals.append(company)
    if branch:
        where.append("branch = %s"); vals.append(branch)
    where_clause = " AND ".join(where)

    # --- Collect data grouped by Executive & Month ---
    sql = f"""
    SELECT
        executive_name,
        DATE_FORMAT({post_f}, '%%Y-%%m') AS month,
        COUNT(name) AS submitted,
        SUM(CASE WHEN {appr_f} IS NOT NULL THEN 1 ELSE 0 END) AS approved,
        SUM(CASE WHEN {sent_f} IS NOT NULL THEN 1 ELSE 0 END) AS agreement_sent,
        SUM(CASE WHEN {sign_f} IS NOT NULL THEN 1 ELSE 0 END) AS signed,
        SUM(CASE WHEN {conv_f} IS NOT NULL THEN 1 ELSE 0 END) AS converted,
        SUM(CASE WHEN {inst_f} IS NOT NULL THEN 1 ELSE 0 END) AS installed,
        SUM(CASE WHEN LOWER(workflow_state)='rejected' THEN 1 ELSE 0 END) AS rejected
    FROM `tabATM Leads`
    WHERE {where_clause}
      AND {post_f} BETWEEN %s AND %s
    GROUP BY executive_name, month
    ORDER BY month ASC, executive_name ASC
    """

    data = frappe.db.sql(sql, vals + [from_date, to_date], as_dict=True)

    # --- Compute conversion metrics ---
    for row in data:
        row["sub_to_appr_pct"] = _pct(row["approved"], row["submitted"])
        row["appr_to_sent_pct"] = _pct(row["agreement_sent"], row["approved"])
        row["sent_to_sign_pct"] = _pct(row["signed"], row["agreement_sent"])
        row["sign_to_conv_pct"] = _pct(row["converted"], row["signed"])
        row["conv_to_inst_pct"] = _pct(row["installed"], row["converted"])
        row["rejection_ratio"] = _pct(row["rejected"], row["submitted"])

    # --- Columns ---
    columns = [
        {"fieldname": "month", "label": "Month", "fieldtype": "Data", "width": 90},
        {"fieldname": "executive_name", "label": "Sales Agent", "fieldtype": "Link", "options": "Sales Agent", "width": 160},
        {"fieldname": "submitted", "label": "Submitted", "fieldtype": "Int", "width": 100},
        {"fieldname": "approved", "label": "Approved", "fieldtype": "Int", "width": 100},
        {"fieldname": "agreement_sent", "label": "Agreement Sent", "fieldtype": "Int", "width": 120},
        {"fieldname": "signed", "label": "Signed", "fieldtype": "Int", "width": 90},
        {"fieldname": "converted", "label": "Converted", "fieldtype": "Int", "width": 90},
        {"fieldname": "installed", "label": "Installed", "fieldtype": "Int", "width": 100},
        {"fieldname": "rejected", "label": "Rejected", "fieldtype": "Int", "width": 100},
        {"fieldname": "sub_to_appr_pct", "label": "Submitted → Approved %", "fieldtype": "Percent", "width": 150},
        {"fieldname": "appr_to_sent_pct", "label": "Approved → Sent %", "fieldtype": "Percent", "width": 150},
        {"fieldname": "sent_to_sign_pct", "label": "Sent → Signed %", "fieldtype": "Percent", "width": 150},
        {"fieldname": "sign_to_conv_pct", "label": "Signed → Converted %", "fieldtype": "Percent", "width": 150},
        {"fieldname": "conv_to_inst_pct", "label": "Converted → Installed %", "fieldtype": "Percent", "width": 150},
        {"fieldname": "rejection_ratio", "label": "Rejection %", "fieldtype": "Percent", "width": 100},
    ]

    # --- Chart (Top 5 Executives by Conversion Rate) ---
    # For visualization, aggregate per executive across months
    perf = {}
    for r in data:
        if not r["executive_name"]:
            continue
        perf.setdefault(r["executive_name"], {"signed": 0, "converted": 0})
        perf[r["executive_name"]]["signed"] += r["signed"]
        perf[r["executive_name"]]["converted"] += r["converted"]

    execs, conv_rates = [], []
    for name, d in sorted(perf.items(), key=lambda x: x[1]["converted"], reverse=True)[:5]:
        execs.append(name)
        conv_rates.append(_pct(d["converted"], d["signed"]))

    chart = {
        "type": "bar",
        "data": {
            "labels": execs,
            "datasets": [{"name": "Signed → Converted %", "values": conv_rates}],
        },
        "colors": ["#16a34a"],
    }

    # --- Summary ---
    total_execs = len({d["executive_name"] for d in data})
    report_summary = [
        {"label": "Executives", "value": total_execs, "indicator": "blue"},
        {"label": "Best Conversion %", "value": max(conv_rates) if conv_rates else 0, "indicator": "green"},
    ]

    msg = (
        f"Window: <b>{from_date.strftime('%d-%m-%Y')}</b> → <b>{to_date.strftime('%d-%m-%Y')}</b>. "
        f"Branch: <b>{branch or 'All'}</b> | Company: <b>{company or 'All'}</b>."
    )

    return columns, data, msg, chart, report_summary
