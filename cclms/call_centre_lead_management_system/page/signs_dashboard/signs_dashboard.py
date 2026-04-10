# Copyright (c) 2026, Galaxy and contributors
# For license information, please see license.txt
#
# Signs & Attribution Dashboard — backend APIs
# ─────────────────────────────────────────────
# Data sources:
#   • tabAgent Stage Ledger  — immutable transition log (days_in_prev_state, from/to_state)
#   • tabSigns               — sign records (lead agent snapshot + closing agent for commission)
#   • tabATM Leads           — live pipeline snapshot
#
# All APIs are @frappe.whitelist() and return plain dicts/lists.

import frappe
from frappe.utils import getdate, get_first_day, get_last_day, add_months


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _period(from_date=None, to_date=None):
    """Default to current month when no dates given."""
    today = getdate()
    start = getdate(from_date) if from_date else get_first_day(today)
    end   = getdate(to_date)   if to_date   else get_last_day(today)
    return str(start), str(end)


# ─────────────────────────────────────────────────────────────
# 1. Stage Velocity — avg days in each state before transitioning out
# ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_stage_velocity(from_date=None, to_date=None, company=None, branch=None):
    """
    From Agent Stage Ledger: for each to_state, return
    avg days spent in the previous state (days_in_prev_state).

    This answers: "How long does it take us to move a lead through each stage?"
    """
    start, end = _period(from_date, to_date)

    where = ["asl.stage_date BETWEEN %(start)s AND %(end)s", "asl.days_in_prev_state > 0"]
    params = {"start": start, "end": end}

    if company:
        where.append("asl.company = %(company)s")
        params["company"] = company
    if branch:
        where.append("asl.branch = %(branch)s")
        params["branch"] = branch

    rows = frappe.db.sql(
        f"""
        SELECT
            asl.to_state                            AS state,
            ROUND(AVG(asl.days_in_prev_state), 1)   AS avg_days,
            COUNT(*)                                AS transitions,
            MIN(asl.days_in_prev_state)             AS min_days,
            MAX(asl.days_in_prev_state)             AS max_days
        FROM `tabAgent Stage Ledger` asl
        WHERE {' AND '.join(where)}
          AND asl.to_state NOT LIKE '[Sign Event]%%'
        GROUP BY asl.to_state
        ORDER BY avg_days DESC
        """,
        params,
        as_dict=True,
    )
    return rows


# ─────────────────────────────────────────────────────────────
# 2. Signs Summary — totals + pending attribution  
# ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_signs_summary(from_date=None, to_date=None, company=None):
    """
    Returns:
    {
      total_signs         — Signs records created in period
      pending_attribution — Signs with no closing_agent (commission not assigned yet)
      attributed          — Signs with closing_agent filled
      pending_records     — [list] of pending Signs for the action table
    }
    """
    start, end = _period(from_date, to_date)

    where = ["sign_date BETWEEN %(start)s AND %(end)s"]
    params = {"start": start, "end": end}
    if company:
        where.append("company = %(company)s")
        params["company"] = company

    rows = frappe.db.sql(
        f"""
        SELECT
            name,
            atm_leads,
            sign_date,
            employee          AS lead_agent,
            closing_agent,
            company,
            branch,
            business_name,
            state_code
        FROM `tabSigns`
        WHERE {' AND '.join(where)}
        ORDER BY sign_date DESC
        """,
        params,
        as_dict=True,
    )

    pending = [r for r in rows if not r.get("closing_agent")]
    attributed = [r for r in rows if r.get("closing_agent")]

    return {
        "total_signs": len(rows),
        "pending_attribution": len(pending),
        "attributed": len(attributed),
        "pending_records": pending,
    }


# ─────────────────────────────────────────────────────────────
# 3. Agent Attribution — who created vs who closed
# ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_agent_attribution(from_date=None, to_date=None, company=None):
    """
    Per Sales Agent shows:
    - as_lead_agent    : #Signs where they were the assigned agent at sign time
    - as_closing_agent : #Signs where manager selected them as the deal closer (commission)
    - diff             : closing - lead (positive = closer more deals than they brought)
    """
    start, end = _period(from_date, to_date)

    where = ["sign_date BETWEEN %(start)s AND %(end)s"]
    params = {"start": start, "end": end}
    if company:
        where.append("company = %(company)s")
        params["company"] = company

    cond = " AND ".join(where)

    lead_rows = frappe.db.sql(
        f"""
        SELECT employee AS agent, COUNT(*) AS cnt
        FROM `tabSigns`
        WHERE {cond} AND IFNULL(employee,'') != ''
        GROUP BY employee
        """,
        params, as_dict=True,
    )

    closer_rows = frappe.db.sql(
        f"""
        SELECT closing_agent AS agent, COUNT(*) AS cnt
        FROM `tabSigns`
        WHERE {cond} AND IFNULL(closing_agent,'') != ''
        GROUP BY closing_agent
        """,
        params, as_dict=True,
    )

    agent_map = {}

    def _ensure(a):
        if a not in agent_map:
            agent_map[a] = {"agent": a, "as_lead_agent": 0, "as_closing_agent": 0}
        return agent_map[a]

    for r in lead_rows:
        _ensure(r.agent)["as_lead_agent"] = r.cnt
    for r in closer_rows:
        _ensure(r.agent)["as_closing_agent"] = r.cnt

    # Resolve agent display names
    agent_ids = list(agent_map.keys())
    if agent_ids:
        sa_list = frappe.db.get_all(
            "Sales Agent",
            filters={"name": ["in", agent_ids]},
            fields=["name", "agent_name", "full_name"],
        )
        sa_map = {s.name: s for s in sa_list}
        for key, rec in agent_map.items():
            sa = sa_map.get(key)
            rec["display_name"] = (sa.full_name or sa.agent_name or key) if sa else key

    rows = list(agent_map.values())
    for r in rows:
        r["diff"] = r["as_closing_agent"] - r["as_lead_agent"]
        r.setdefault("display_name", r["agent"])

    rows.sort(key=lambda x: x["as_closing_agent"] + x["as_lead_agent"], reverse=True)
    return rows


# ─────────────────────────────────────────────────────────────
# 4. Pipeline Snapshot — live state counts from ATM Leads
# ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_pipeline_snapshot(company=None, branch=None):
    """
    Live count of ATM Leads grouped by workflow_state.
    Also returns approval rate, rejection rate, conversion rate.
    """
    where = ["docstatus < 2"]
    params = {}
    if company:
        where.append("company = %(company)s")
        params["company"] = company
    if branch:
        where.append("branch = %(branch)s")
        params["branch"] = branch

    rows = frappe.db.sql(
        f"""
        SELECT
            IFNULL(workflow_state, 'Draft') AS state,
            COUNT(*) AS count
        FROM `tabATM Leads`
        WHERE {' AND '.join(where)}
        GROUP BY workflow_state
        ORDER BY count DESC
        """,
        params,
        as_dict=True,
    )

    state_map = {r.state: r.count for r in rows}
    total = sum(r.count for r in rows)

    def _pct(n):
        return round(n / total * 100, 1) if total else 0.0

    signed   = state_map.get("Signed", 0)
    approved = state_map.get("Approved", 0)
    rejected = state_map.get("Rejected", 0)
    installed = state_map.get("Installed", 0)

    return {
        "states": rows,
        "total": total,
        "sign_rate":     _pct(signed),
        "approval_rate": _pct(approved),
        "rejection_rate": _pct(rejected),
        "install_rate":  _pct(installed),
    }


# ─────────────────────────────────────────────────────────────
# 5. Approval vs Rejection trend — monthly from Agent Stage Ledger
# ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_approval_rejection_trend(months_back=6, company=None):
    """
    Monthly counts of transitions TO: Approved, Rejected, Signed, Installed
    from Agent Stage Ledger — last N months.

    Returns: { categories: ["2026-01", ...], series: [{name, data}, ...] }
    """
    today = getdate()
    start_month = add_months(today.replace(day=1), -(int(months_back) - 1))

    where = ["stage_date >= %(start)s"]
    params = {"start": str(start_month)}
    if company:
        where.append("company = %(company)s")
        params["company"] = company

    rows = frappe.db.sql(
        f"""
        SELECT
            DATE_FORMAT(stage_date, '%%Y-%%m') AS month,
            to_state,
            COUNT(*) AS cnt
        FROM `tabAgent Stage Ledger`
        WHERE {' AND '.join(where)}
          AND to_state IN ('Approved','Rejected','Signed','Installed','Converted')
        GROUP BY month, to_state
        ORDER BY month ASC
        """,
        params,
        as_dict=True,
    )

    # Build month list
    categories = []
    cur = start_month
    while cur <= today:
        categories.append(f"{cur.year}-{cur.month:02d}")
        cur = add_months(cur, 1)

    series_map = {
        "Approved":  [0] * len(categories),
        "Rejected":  [0] * len(categories),
        "Signed":    [0] * len(categories),
        "Installed": [0] * len(categories),
        "Converted": [0] * len(categories),
    }
    cat_idx = {c: i for i, c in enumerate(categories)}

    for r in rows:
        if r.to_state in series_map and r.month in cat_idx:
            series_map[r.to_state][cat_idx[r.month]] += r.cnt

    COLORS = {
        "Approved":  "#f59e0b",
        "Rejected":  "#ef4444",
        "Signed":    "#10b981",
        "Installed": "#22c55e",
        "Converted": "#0ea5e9",
    }

    series = [
        {"name": k, "data": v, "color": COLORS.get(k, "#6b7280")}
        for k, v in series_map.items()
    ]

    return {"categories": categories, "series": series}
