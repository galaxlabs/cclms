# Copyright (c) 2026, Galaxy and contributors
# For license information, please see license.txt
#
# Employee Stage Status Report
# ─────────────────────────────
# Answers: "Right now, how many leads does EACH employee have at each workflow
# stage, and how long have they been there?"
#
# Source of truth: live ATM Leads.workflow_state  (no rebuild needed)
# Aging:          days since post_date when in Draft/first transition
#                 OR days since last state-history change_date
#
# Color-coded aging in the "Max Days Stuck" column:
#   ≤ 7  days  → green
#   8-14 days  → amber
#   > 14 days  → red

from datetime import date

import frappe
from frappe.utils import getdate


# Ordered display pipeline for columns
PIPELINE = [
    "Draft",
    "Pending",
    "Approved",
    "Requested for Agreement Sent",
    "Agreement Sent",
    "Pending Sign",
    "Signed",
    "Converted",
    "Installed",
    "Rejected",
    "Re Approval",
    "Not Qualified",
    "Signed Rejected",
    "Needs Reanalysis",
    "Resigned",
    "Disputed",
    "Call Back",
    "Called",
    "Interested",
    "Not Interested",
    "Cancelled",
    "Hide",
    "installed/Removed",
]


def _colorize_days(days: int) -> str:
    if days <= 7:
        color = "#16a34a"
    elif days <= 14:
        color = "#f59e0b"
    else:
        color = "#ef4444"
    return f'<span style="color:{color};font-weight:600">{days}</span>'


def execute(filters=None):
    filters = filters or {}
    today = date.today()

    # ── Optional filters ────────────────────────────────────────────────────
    company = filters.get("company")
    branch = filters.get("branch")
    executive_name = filters.get("executive_name")

    where_parts = ["l.docstatus < 2"]
    params: dict = {}

    if company:
        where_parts.append("l.company = %(company)s")
        params["company"] = company
    if branch:
        where_parts.append("l.branch = %(branch)s")
        params["branch"] = branch
    if executive_name:
        where_parts.append("l.executive_name = %(executive_name)s")
        params["executive_name"] = executive_name

    where_sql = " AND ".join(where_parts)

    # ── Fetch live ATM Leads ────────────────────────────────────────────────
    leads = frappe.db.sql(
        f"""
        SELECT
            l.name,
            l.executive_name,
            COALESCE(sa.full_name, l.executive_name) AS agent_label,
            sa.agent_name                             AS pseudo_name,
            l.branch,
            l.company,
            COALESCE(l.workflow_state, 'Draft')       AS workflow_state,
            l.post_date
        FROM `tabATM Leads` l
        LEFT JOIN `tabSales Agent` sa ON sa.name = l.executive_name
        WHERE {where_sql}
        ORDER BY l.executive_name, l.name
        """,
        params,
        as_dict=True,
    )

    if not leads:
        return _get_columns(), [], "No leads found for the selected filters.", None, []

    # ── Last state-change date per lead (from child table) ──────────────────
    lead_names = [r["name"] for r in leads]
    history_rows = frappe.db.sql(
        """
        SELECT parent, MAX(change_date) AS last_change
        FROM `tabATM Lead State History`
        WHERE parent IN %(names)s
        GROUP BY parent
        """,
        {"names": lead_names},
        as_dict=True,
    )
    last_change_map = {r["parent"]: getdate(r["last_change"]) for r in history_rows}

    # ── Build per-agent stage counts ────────────────────────────────────────
    # Structure: {agent_key: {"label": ..., "pseudo": ..., "branch": ...,
    #                          "company": ..., states: {state: count},
    #                          "max_days": int}}
    agents: dict = {}

    for lead in leads:
        key = lead["executive_name"] or "Unknown"
        if key not in agents:
            agents[key] = {
                "agent_label": lead["agent_label"] or key,
                "pseudo_name": lead["pseudo_name"] or "",
                "branch": lead["branch"] or "",
                "company": lead["company"] or "",
                "states": {},
                "max_days": 0,
                "total": 0,
            }

        state = lead["workflow_state"]
        agents[key]["states"][state] = agents[key]["states"].get(state, 0) + 1
        agents[key]["total"] += 1

        # Compute days stuck in current state
        last_change = last_change_map.get(lead["name"])
        if last_change:
            days = (today - last_change).days
        elif lead["post_date"]:
            days = (today - getdate(lead["post_date"])).days
        else:
            days = 0

        if days > agents[key]["max_days"]:
            agents[key]["max_days"] = days

    # ── Build report rows ───────────────────────────────────────────────────
    data = []
    for key, info in sorted(agents.items(), key=lambda x: x[1]["agent_label"]):
        row = {
            "agent": info["agent_label"],
            "pseudo_name": info["pseudo_name"],
            "branch": info["branch"],
            "company": info["company"],
            "total": info["total"],
            "max_days_html": _colorize_days(info["max_days"]),
        }
        for state in PIPELINE:
            # fieldname: lowercase, spaces→underscore, slashes→underscore
            fn = "s_" + state.lower().replace(" ", "_").replace("/", "_")
            row[fn] = info["states"].get(state, 0) or ""
        data.append(row)

    # ── Chart: top 12 agents by total leads ─────────────────────────────────
    top = sorted(data, key=lambda r: r["total"], reverse=True)[:12]
    chart = {
        "type": "bar",
        "data": {
            "labels": [r["agent"] for r in top],
            "datasets": [
                {
                    "name": "Total Active",
                    "values": [r["total"] for r in top],
                }
            ],
        },
        "colors": ["#2563eb"],
    }

    # ── Summary tiles ─────────────────────────────────────────────────────
    total_leads = len(leads)
    pending_cnt = sum(
        info["states"].get("Pending", 0)
        + info["states"].get("Approved", 0)
        + info["states"].get("Agreement Sent", 0)
        for info in agents.values()
    )
    signed_cnt = sum(info["states"].get("Signed", 0) for info in agents.values())
    installed_cnt = sum(info["states"].get("Installed", 0) for info in agents.values())
    stale_agents = sum(1 for info in agents.values() if info["max_days"] > 14)

    report_summary = [
        {"label": "Total Leads",      "value": total_leads,    "indicator": "blue",   "datatype": "Int"},
        {"label": "In Pipeline",      "value": pending_cnt,    "indicator": "blue",   "datatype": "Int"},
        {"label": "Signed",           "value": signed_cnt,     "indicator": "green",  "datatype": "Int"},
        {"label": "Installed",        "value": installed_cnt,  "indicator": "green",  "datatype": "Int"},
        {"label": "Agents >14d Stuck","value": stale_agents,   "indicator": "red",    "datatype": "Int"},
    ]

    return _get_columns(), data, None, chart, report_summary


def _get_columns():
    cols = [
        {"label": "Agent",           "fieldname": "agent",          "fieldtype": "Data",    "width": 180},
        {"label": "Pseudo",          "fieldname": "pseudo_name",    "fieldtype": "Data",    "width": 100},
        {"label": "Branch",          "fieldname": "branch",         "fieldtype": "Data",    "width": 100},
        {"label": "Company",         "fieldname": "company",        "fieldtype": "Data",    "width": 130},
        {"label": "Total",           "fieldname": "total",          "fieldtype": "Int",     "width": 70},
        {"label": "Max Days Stuck",  "fieldname": "max_days_html",  "fieldtype": "HTML",    "width": 110},
    ]
    for state in PIPELINE:
        fn = "s_" + state.lower().replace(" ", "_").replace("/", "_")
        cols.append({
            "label": state,
            "fieldname": fn,
            "fieldtype": "Data",
            "width": 80,
        })
    return cols
