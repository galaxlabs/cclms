# Copyright (c) 2025, Galaxy and contributors
# For license information, please see license.txt

# cclms/cclms/report/workflow_transitions_playground/workflow_transitions_playground.py
from datetime import date
from typing import Dict, Any, List, Tuple
import frappe

# ====== CONFIG ======
DOCTYPE = "ATM Leads"   # change if your doctype has a different name

# (from_state, to_state, date_field_indicating_this_transition_happened)
EDGE_MAP: List[Tuple[str, str, str]] = [
    ("Draft", "Submitted",         "post_date"),
    ("Submitted", "Pending",       "submitted_date"),
    ("Pending", "Approved",        "approved_date"),
    ("Pending", "Rejected",        "rejected_date"),
    ("Approved", "Agreement Sent", "agreement_sent_date"),
    ("Agreement Sent", "Signed",   "sign_date"),
    ("Signed", "Converted",        "converted_date"),
    ("Converted", "Installed",     "installed_date"),
    ("Rejected", "ReApproval",     "reapproval_date"),
    ("ReApproval", "Approved",     "approved_date"),
]

# for conversion% denominator (to_stage -> denom_stage)
DENOM_STAGE = {
    "Submitted": "Created",          # we'll use Created (post_date) as denom
    "Pending":   "Submitted",
    "Approved":  "Pending",
    "Rejected":  "Pending",
    "Agreement Sent": "Approved",
    "Signed":    "Agreement Sent",
    "Converted": "Signed",
    "Installed": "Converted",
    "ReApproval":"Rejected",
}

# dataset colors (frappe-charts = per-series colors)
DATASET_COLORS = ["#334155", "#10b981"]  # counts, conversion%
# We'll still keep a per-stage color map for other UIs / future:
STAGE_COLORS = {
    "Submitted": "#334155",
    "Pending": "#3b82f6",
    "Approved": "#f59e0b",
    "Rejected": "#ef4444",
    "Agreement Sent": "#005c08",  # your requested green
    "Signed": "#10b981",
    "Converted": "#0ea5e9",
    "Installed": "#22c55e",
    "ReApproval": "#8b5cf6",
}

def _date_window(filters: Dict[str, Any]):
    start = filters.get("start_date") or str(date.today().replace(day=1))
    end   = filters.get("end_date")   or str(date.today())
    return start, end

def _base_where(filters: Dict[str, Any]):
    where = ["1=1"]
    params: Dict[str, Any] = {}
    if filters.get("company"):
        where.append("IFNULL(company,'') = %(company)s")
        params["company"] = filters["company"]
    if filters.get("executive_name"):
        where.append("IFNULL(executive_name,'') = %(executive_name)s")
        params["executive_name"] = filters["executive_name"]
    if filters.get("state"):
        where.append("(IFNULL(state_code,'') = %(state)s OR IFNULL(state,'') = %(state)s)")
        params["state"] = filters["state"]
    if str(filters.get("exclude_drafts", 1)).lower() in ("1", "true", "yes"):
        where.append("IFNULL(workflow_state,'') != 'Draft'")
    return where, params

def _count_created(start: str, end: str, where: List[str], params: Dict[str, Any]) -> int:
    sql = f"""
        SELECT COUNT(*) AS c
        FROM `tab{DOCTYPE}`
        WHERE {" AND ".join(where)}
          AND post_date IS NOT NULL
          AND DATE(post_date) BETWEEN %(start)s AND %(end)s
    """
    row = frappe.db.sql(sql, {**params, "start": start, "end": end}, as_dict=True)[0]
    return int(row["c"] or 0)

def _count_transition(date_field: str, start: str, end: str, where: List[str], params: Dict[str, Any]) -> int:
    sql = f"""
        SELECT COUNT(*) AS c
        FROM `tab{DOCTYPE}`
        WHERE {" AND ".join(where)}
          AND `{date_field}` IS NOT NULL
          AND DATE(`{date_field}`) BETWEEN %(start)s AND %(end)s
    """
    row = frappe.db.sql(sql, {**params, "start": start, "end": end}, as_dict=True)[0]
    return int(row["c"] or 0)

def execute(filters: Dict[str, Any] = None):
    """
    Returns: columns, data, message, chart, report_summary
    Filters:
      - start_date, end_date (YYYY-MM-DD)
      - company (Link Operator Companies)
      - executive_name (Link Sales Agent)
      - state (CA or California)
      - exclude_drafts (Check)
    """
    filters = filters or {}
    start, end = _date_window(filters)
    where, params = _base_where(filters)

    # ensure date fields exist; skip missing
    have = {df.fieldname for df in frappe.get_meta(DOCTYPE).fields}
    edges = [e for e in EDGE_MAP if e[2] in have]

    # Created count (for Submitted denom)
    created_count = _count_created(start, end, where, params)

    # per-edge counts
    edge_counts: Dict[Tuple[str, str], int] = {}
    stage_counts: Dict[str, int] = {}  # count reaching each to_state
    for frm, to, df in edges:
        c = _count_transition(df, start, end, where, params)
        if c:
            edge_counts[(frm, to)] = c
            stage_counts[to] = stage_counts.get(to, 0) + c

    # denominators per stage
    denom_for_stage: Dict[str, int] = {}
    for stage, denom_stage in DENOM_STAGE.items():
        if denom_stage == "Created":
            denom_for_stage[stage] = created_count
        else:
            # denom = total that reached denom_stage in window
            denom_for_stage[stage] = stage_counts.get(denom_stage, 0)

    # build rows (colored conversion cell)
    columns = [
        {"label": "From",       "fieldname": "from_state", "fieldtype": "Data", "width": 140},
        {"label": "To",         "fieldname": "to_state",   "fieldtype": "Data", "width": 160},
        {"label": "Date Field", "fieldname": "date_field", "fieldtype": "Data", "width": 160},
        {"label": "Count",      "fieldname": "count",      "fieldtype": "Int",  "width": 90},
        {"label": "Conversion %","fieldname": "conv_html", "fieldtype": "HTML", "width": 110},
    ]

    def colorize_pct(pct: float) -> str:
        # thresholds: >=70 green, >=30 amber, else red
        if pct >= 70: col = "#16a34a"
        elif pct >= 30: col = "#f59e0b"
        else: col = "#ef4444"
        return f'<span style="color:{col};font-weight:600">{round(pct)}%</span>'

    rows: List[Dict[str, Any]] = []
    for frm, to, df in edges:
        c = edge_counts.get((frm, to), 0)
        denom = max(denom_for_stage.get(to, 0), 0)
        pct = (100.0 * c / denom) if denom > 0 else 0.0
        rows.append({
            "from_state": frm,
            "to_state": to,
            "date_field": df,
            "count": c,
            "conv_html": colorize_pct(pct),
        })

    # chart: two datasets (counts, conversion%)
    labels = list(stage_counts.keys())
    counts = [stage_counts[k] for k in labels]
    convs  = []
    for lbl in labels:
        c = stage_counts.get(lbl, 0)
        denom = max(denom_for_stage.get(lbl, 0), 0)
        pct = (100.0 * c / denom) if denom > 0 else 0.0
        convs.append(round(pct, 2))

    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "Counts",        "values": counts},
                {"name": "Conversion %",  "values": convs},
            ]
        },
        "type": "bar",                 # change to "line" / "pie" if you want
        "colors": DATASET_COLORS,      # series colors (counts, conversion)
        "axisOptions": {"xIsSeries": 1}
    }

    # report summary tiles (example set; adjust if you need more)
    def _safe_get(stage: str) -> int:
        return int(stage_counts.get(stage, 0) or 0)

    report_summary = [
        {"value": f"{created_count}",        "label":"Total Created", "datatype": "Int"},
        {"value": f"{_safe_get('Approved')}",       "label": "Approved",      "datatype": "Int"},
        {"value": f"{_safe_get('Agreement Sent')}", "label": "Agreement Sent","datatype": "Int"},
        {"value": f"{_safe_get('Signed')}",         "label": "Signed",        "datatype": "Int"},
        {"value": f"{_safe_get('Converted')}",      "label": "Converted",     "datatype": "Int"},
    ]

    # message (like the article shows)
    msg = (
        f"Window: <b>{frappe.utils.format_date(start)}</b> → "
        f"<b>{frappe.utils.format_date(end)}</b>. "
        f"Counts are based on the destination <i>date field</i> occurring inside the window. "
        f"Conversion% uses prior stage as denominator "
        f"(e.g., Agreement Sent ÷ Approved, Signed ÷ Agreement Sent, etc.; "
        f"Submitted ÷ Created)."
    )

    return columns, rows, msg, chart, report_summary
