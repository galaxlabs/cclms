import frappe
from typing import Dict, Any, Optional, List
from datetime import datetime


def _parse_date(s: Optional[str]) -> Optional[str]:
    return s.strip() if s else None


def _slug(name: str) -> str:
    return name.replace(" ", "_").lower()


def execute(filters: Optional[Dict[str, Any]] = None):
    """
    Task Force Roster – Executive Dashboard
    ---------------------------------------
    ✅ Filters strictly by sign_date
    ✅ Hides agents & companies with no leads
    ✅ Grand Total row sums accurately (numeric)
    ✅ Chart type toggle: bar | line
    ✅ Chart group toggle: agent | date
    ✅ Auto month aggregation for long ranges
    """
    filters = filters or {}
    from_date = _parse_date(filters.get("from_date"))
    to_date = _parse_date(filters.get("to_date"))
    branch = filters.get("branch")
    company_filter = filters.get("company")
    chart_type = (filters.get("chart_type") or "bar").lower()
    chart_group = (filters.get("chart_group") or "agent").lower()

    # --- Get Operator Companies ---
    if company_filter:
        companies = [company_filter]
    else:
        companies = [r.name for r in frappe.get_all("Operator Companies")]

    # --- Sales Agents ---
    where_agent = ["1=1"]
    vals_agent = []
    if branch:
        where_agent.append("branch=%s")
        vals_agent.append(branch)

    agents = frappe.db.sql(
        f"""
        SELECT agent_name, full_name,
               IFNULL(kpi_minimum,0) AS kpi_minimum,
               IFNULL(kpi_maximum,0) AS kpi_maximum
        FROM `tabSales Agent`
        WHERE {" AND ".join(where_agent)}
        ORDER BY agent_name
        """,
        vals_agent,
        as_dict=True,
    )
    agent_map = {a.agent_name: a for a in agents}
    if not agent_map:
        return _columns([]), [], "No Sales Agents found", None, None

    # --- Leads Signed within Date Range ---
    where = ["workflow_state='Signed'"]
    vals = []
    if from_date and to_date:
        where.append("sign_date BETWEEN %s AND %s")
        vals += [from_date, to_date]
    elif from_date:
        where.append("sign_date >= %s")
        vals.append(from_date)
    elif to_date:
        where.append("sign_date <= %s")
        vals.append(to_date)
    if company_filter:
        where.append("company=%s")
        vals.append(company_filter)

    lead_rows = frappe.db.sql(
        f"""
        SELECT executive_name, company, DATE(sign_date) AS sdate, COUNT(*) AS cnt
        FROM `tabATM Leads`
        WHERE {" AND ".join(where)}
        GROUP BY executive_name, company, DATE(sign_date)
        """,
        vals,
        as_dict=True,
    )

    # --- Aggregate ---
    per_agent: Dict[str, Dict[str, int]] = {}
    totals_per_company = {c: 0 for c in companies}
    total_signed = 0
    per_day: Dict[str, int] = {}

    for r in lead_rows:
        ag = r.executive_name
        comp = r.company
        cnt = int(r.cnt or 0)
        if ag not in agent_map:
            continue
        per_agent.setdefault(ag, {})
        per_agent[ag][comp] = per_agent[ag].get(comp, 0) + cnt
        totals_per_company[comp] = totals_per_company.get(comp, 0) + cnt
        total_signed += cnt

        dkey = str(r.sdate)
        per_day[dkey] = per_day.get(dkey, 0) + cnt

    # --- Remove Empty Companies ---
    companies = [c for c in companies if totals_per_company.get(c, 0) > 0]

    # --- Build Rows ---
    rows = []
    for ag, meta in agent_map.items():
        comp_data = per_agent.get(ag, {})
        signed_total = sum(comp_data.get(c, 0) for c in companies)
        if signed_total == 0:
            continue

        kpi_min = int(meta.kpi_minimum or 0)
        kpi_max = int(meta.kpi_maximum or 0)
        achv = round((signed_total / kpi_max) * 100, 1) if kpi_max else 0.0
        color = "#16a34a" if achv >= 100 else "#f59e0b" if achv >= 75 else "#dc2626"

        row = {
            "agent_name": ag,
            "full_name": meta.full_name,
            "signed_total": signed_total,  # numeric
            "kpi_minimum": kpi_min,
            "kpi_maximum": kpi_max,
            "kpi_ach": f"<span style='color:{color};font-weight:600'>{achv}%</span>",
        }
        for c in companies:
            row[f"c_{_slug(c)}"] = comp_data.get(c, 0)
        rows.append(row)

    # --- Grand Total Row (Numeric) ---
    if rows:
        grand_signed_total = sum(r["signed_total"] for r in rows)
        grand_company_totals = {
            c: sum(r.get(f"c_{_slug(c)}", 0) for r in rows)
            for c in companies
        }

        grand = {
            "agent_name": "Grand Total",
            "full_name": "",
            "signed_total": grand_signed_total,
            "kpi_minimum": 0,
            "kpi_maximum": 0,
            "kpi_ach": "",
        }
        for c in companies:
            grand[f"c_{_slug(c)}"] = grand_company_totals[c]
        rows.append(grand)

    columns = _columns(companies)

    # --- Chart (Agent vs Date, auto-month) ---
    if chart_group == "date":
        # auto monthly if range > 45 days
        date_keys = sorted(per_day.keys())
        if from_date and to_date:
            start = datetime.strptime(from_date, "%Y-%m-%d")
            end = datetime.strptime(to_date, "%Y-%m-%d")
            day_diff = (end - start).days
        else:
            day_diff = len(date_keys)

        if day_diff > 45:
            monthly = {}
            for d, v in per_day.items():
                ym = d[:7]  # YYYY-MM
                monthly[ym] = monthly.get(ym, 0) + v
            labels = sorted(monthly.keys())
            values = [monthly[m] for m in labels]
            chart_label = "Signed Leads (by Month)"
        else:
            labels = date_keys
            values = [per_day[d] for d in labels]
            chart_label = "Signed Leads (by Day)"

        chart = {
            "type": chart_type if chart_type in ("bar", "line") else "bar",
            "data": {"labels": labels, "datasets": [{"name": chart_label, "values": values}]},
            "colors": ["#0ea5e9"],
        }

    else:  # by agent
        labels = [r["agent_name"] for r in rows if isinstance(r.get("signed_total"), int)]
        values = [r["signed_total"] for r in rows if isinstance(r.get("signed_total"), int)]
        chart = {
            "type": chart_type if chart_type in ("bar", "line") else "bar",
            "data": {"labels": labels, "datasets": [{"name": "Signed (by Agent)", "values": values}]},
            "colors": ["#0ea5e9"],
        }

    # --- Summary ---
    summary = [
        {"label": "Signed (period)", "value": total_signed, "indicator": "green"},
        {"label": "Active Agents", "value": max(len(rows) - 1, 0), "indicator": "blue"},
        {"label": "Operators", "value": len(companies), "indicator": "gray"},
    ]

    msg = f"Signed leads counted by <b>sign_date</b> ({from_date} → {to_date})."
    return columns, rows, msg, chart, summary


def _columns(companies: List[str]) -> List[Dict[str, Any]]:
    cols = [
        {"fieldname": "agent_name", "label": "Agent Name", "fieldtype": "Data", "width": 160},
        {"fieldname": "full_name", "label": "Full Name", "fieldtype": "Data", "width": 180},
        {"fieldname": "signed_total", "label": "Signed Total", "fieldtype": "Int", "width": 110},
    ]
    for c in companies:
        cols.append({
            "fieldname": f"c_{_slug(c)}",
            "label": c,
            "fieldtype": "Int",
            "width": 120,
        })
    cols += [
        {"fieldname": "kpi_minimum", "label": "KPI Min", "fieldtype": "Int", "width": 80},
        {"fieldname": "kpi_maximum", "label": "KPI Max", "fieldtype": "Int", "width": 80},
        {"fieldname": "kpi_ach", "label": "% Achieved", "fieldtype": "HTML", "width": 90},
    ]
    return cols
