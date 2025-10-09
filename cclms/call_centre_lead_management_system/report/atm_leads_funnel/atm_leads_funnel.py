import frappe
from datetime import date, datetime
from calendar import monthrange
from typing import List, Tuple, Dict, Any, Optional

# ---------- Utilities ----------
def _parse_date(s: Optional[str]) -> Optional[date]:
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None

def _month_start(d: date) -> date:
    return d.replace(day=1)

def _month_end(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])

def _iter_months(from_dt: date, to_dt: date) -> List[Tuple[str, date, date]]:
    """Return list of (label, start, end) per month."""
    months = []
    cur = _month_start(from_dt)
    while cur <= to_dt:
        months.append((f"{cur.year}-{cur.month:02d}", cur, _month_end(cur)))
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return months

def _count_between(col: str, start: date, end: date, where: List[str], vals: List[Any]) -> int:
    if not col:
        return 0
    sql = f"SELECT COUNT(name) FROM `tabATM Leads` WHERE {' AND '.join(where)} AND {col} BETWEEN %s AND %s"
    return frappe.db.sql(sql, vals + [str(start), str(end)])[0][0]

def _pct(n, d):
    return round((n / d) * 100, 2) if d else 0.0

# ---------- Report ----------
def execute(filters: Optional[Dict[str, Any]] = None):
    """ATM Leads Funnel with true Date→Date support"""
    filters = filters or {}
    today = date.today()

    from_date = _parse_date(filters.get("from_date")) or date(today.year, 1, 1)
    to_date = _parse_date(filters.get("to_date")) or today
    company = filters.get("company")
    executive_name = filters.get("executive_name")
    branch = filters.get("branch")

    # ---- Field map ----
    post_f = "post_date"
    appr_f = "approve_date"
    sent_f = "agreement_sent_date"
    sign_f = "sign_date"
    conv_f = "convert_date"
    inst_f = "install_date"

    # ---- Static WHERE ----
    where = ["IFNULL(workflow_state,'') <> 'Draft'", "docstatus < 2"]
    vals: List[Any] = []
    if company:
        where.append("company = %s"); vals.append(company)
    if executive_name:
        where.append("executive_name = %s"); vals.append(executive_name)
    if branch:
        where.append("branch = %s"); vals.append(branch)

    # ---- Decide: Monthly or direct Date-to-Date ----
    total_days = (to_date - from_date).days + 1
    monthly_mode = total_days > 15  # if less than ~half a month, do not aggregate by month

    rows, chart_labels = [], []
    s_submitted, s_approved, s_sent, s_signed, s_converted, s_installed, s_rejected = [], [], [], [], [], [], []
    totals = dict(sub=0, appr=0, sent=0, sign=0, conv=0, inst=0, rej=0)

    if monthly_mode:
        # -------- Monthly aggregation --------
        ranges = _iter_months(from_date, to_date)
    else:
        # -------- Direct single window --------
        ranges = [(f"{from_date} → {to_date}", from_date, to_date)]

    for label, start, end in ranges:
        submitted = _count_between(post_f, start, end, where, vals)
        approved  = _count_between(appr_f, start, end, where, vals)
        sent      = _count_between(sent_f, start, end, where, vals)
        signed    = _count_between(sign_f, start, end, where, vals)
        converted = _count_between(conv_f, start, end, where, vals)
        installed = _count_between(inst_f, start, end, where, vals)
        rejected  = frappe.db.sql(
            f"SELECT COUNT(name) FROM `tabATM Leads` WHERE {' AND '.join(where)} "
            f"AND LOWER(workflow_state)='rejected' AND {post_f} BETWEEN %s AND %s",
            vals + [str(start), str(end)]
        )[0][0]

        row = {
            "period": label,
            "submitted": submitted,
            "approved": approved,
            "agreement_sent": sent,
            "signed": signed,
            "converted": converted,
            "installed": installed,
            "rejected": rejected,
            "sub_to_appr_pct": _pct(approved, submitted),
            "appr_to_sent_pct": _pct(sent, approved),
            "sent_to_sign_pct": _pct(signed, sent),
            "sign_to_conv_pct": _pct(converted, signed),
            "conv_to_inst_pct": _pct(installed, converted),
            "rejection_ratio": _pct(rejected, submitted),
        }
        rows.append(row)

        chart_labels.append(label)
        s_submitted.append(submitted)
        s_approved.append(approved)
        s_sent.append(sent)
        s_signed.append(signed)
        s_converted.append(converted)
        s_installed.append(installed)
        s_rejected.append(rejected)

        totals["sub"] += submitted
        totals["appr"] += approved
        totals["sent"] += sent
        totals["sign"] += signed
        totals["conv"] += converted
        totals["inst"] += installed
        totals["rej"] += rejected

    # ---- Columns ----
    columns = [
        {"fieldname": "period", "label": "Period", "fieldtype": "Data", "width": 150},
        {"fieldname": "submitted", "label": "Submitted", "fieldtype": "Int"},
        {"fieldname": "approved", "label": "Approved", "fieldtype": "Int"},
        {"fieldname": "agreement_sent", "label": "Agreement Sent", "fieldtype": "Int"},
        {"fieldname": "signed", "label": "Signed", "fieldtype": "Int"},
        {"fieldname": "converted", "label": "Converted", "fieldtype": "Int"},
        {"fieldname": "installed", "label": "Installed", "fieldtype": "Int"},
        {"fieldname": "rejected", "label": "Rejected", "fieldtype": "Int"},
        {"fieldname": "sub_to_appr_pct", "label": "Submitted → Approved %", "fieldtype": "Percent"},
        {"fieldname": "appr_to_sent_pct", "label": "Approved → Agreement Sent %", "fieldtype": "Percent"},
        {"fieldname": "sent_to_sign_pct", "label": "Agreement Sent → Signed %", "fieldtype": "Percent"},
        {"fieldname": "sign_to_conv_pct", "label": "Signed → Converted %", "fieldtype": "Percent"},
        {"fieldname": "conv_to_inst_pct", "label": "Converted → Installed %", "fieldtype": "Percent"},
        {"fieldname": "rejection_ratio", "label": "Rejection %", "fieldtype": "Percent"},
    ]

    # ---- Chart ----
    chart = {
        "type": "bar" if monthly_mode else "line",
        "data": {
            "labels": chart_labels,
            "datasets": [
                {"name": "Submitted", "values": s_submitted},
                {"name": "Approved", "values": s_approved},
                {"name": "Agreement Sent", "values": s_sent},
                {"name": "Signed", "values": s_signed},
                {"name": "Converted", "values": s_converted},
                {"name": "Installed", "values": s_installed},
                {"name": "Rejected", "values": s_rejected},
            ],
        },
        "colors": ["#334155", "#16a34a", "#005c08", "#0ea5e9", "#f59e0b", "#a855f7", "#ef4444"],
    }

    # ---- Summary ----
    report_summary = [
        {"label": "Submitted", "value": totals["sub"], "indicator": "blue"},
        {"label": "Approved", "value": totals["appr"], "indicator": "green"},
        {"label": "Agreement Sent", "value": totals["sent"], "indicator": "green"},
        {"label": "Signed", "value": totals["sign"], "indicator": "green"},
        {"label": "Converted", "value": totals["conv"], "indicator": "green"},
        {"label": "Installed", "value": totals["inst"], "indicator": "green"},
        {"label": "Rejected", "value": totals["rej"], "indicator": "red"},
    ]

    message = (
        f"Window: <b>{from_date.strftime('%d-%m-%Y')}</b> → <b>{to_date.strftime('%d-%m-%Y')}</b>. "
        f"{'Monthly' if monthly_mode else 'Direct date range'} analysis. "
        f"Branch: <b>{branch or 'All'}</b>."
    )

    return columns, rows, message, chart, report_summary

# import frappe
# from datetime import date, datetime
# from calendar import monthrange
# from typing import List, Tuple, Dict, Any, Optional


# # ---------- Utilities ----------
# def _parse_date(s: Optional[str]) -> Optional[date]:
#     if not s:
#         return None
#     return datetime.strptime(s, "%Y-%m-%d").date()

# def _month_start(d: date) -> date:
#     return d.replace(day=1)

# def _month_end(d: date) -> date:
#     return date(d.year, d.month, monthrange(d.year, d.month)[1])

# def _iter_months(from_dt: date, to_dt: date) -> List[Tuple[str, date, date]]:
#     out = []
#     cur = _month_start(from_dt)
#     while cur <= to_dt:
#         out.append((f"{cur.year}-{cur.month:02d}", cur, _month_end(cur)))
#         cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
#     return out

# def _has(col: str) -> bool:
#     return frappe.db.has_column("ATM Leads", col)

# def _count_between(col: str, start: date, end: date, where: List[str], vals: List[Any]) -> int:
#     if not col:
#         return 0
#     sql = f"SELECT COUNT(name) FROM `tabATM Leads` WHERE {' AND '.join(where)} AND {col} BETWEEN %s AND %s"
#     return frappe.db.sql(sql, vals + [str(start), str(end)])[0][0]


# # ---------- Main ----------
# def execute(filters: Optional[Dict[str, Any]] = None):
#     """
#     ATM Leads Funnel (Post-Date Based)
#     - Submitted = count by post_date
#     - All subsequent stages by their respective date fields
#     - Adds Rejected count + Rejection ratio
#     - Excludes Draft
#     """
#     filters = filters or {}

#     today = date.today()
#     from_date = _parse_date(filters.get("from_date")) or date(today.year, 1, 1)
#     to_date = _parse_date(filters.get("to_date")) or today
#     company = filters.get("company")
#     executive_name = filters.get("executive_name")

#     # ---- Field map ----
#     post_f = "post_date"
#     appr_f = "approve_date" if _has("approve_date") else None
#     sent_f = "agreement_sent_date" if _has("agreement_sent_date") else None
#     sign_f = "sign_date" if _has("sign_date") else None
#     conv_f = "convert_date" if _has("convert_date") else None
#     inst_f = "install_date" if _has("install_date") else None

#     # ---- Static WHERE ----
#     where = ["IFNULL(workflow_state,'') <> 'Draft'", "docstatus < 2"]
#     vals: List[Any] = []
#     if company:
#         where.append("company = %s"); vals.append(company)
#     if executive_name:
#         where.append("executive_name = %s"); vals.append(executive_name)

#     months = _iter_months(from_date, to_date)
#     rows, chart_labels = [], []
#     s_submitted, s_approved, s_sent, s_signed, s_converted, s_installed, s_rejected = [], [], [], [], [], [], []

#     totals = dict(sub=0, appr=0, sent=0, sign=0, conv=0, inst=0, rej=0)

#     def pct(n, d): return round((n / d) * 100, 2) if d else 0.0

#     for ym, m_start, m_end in months:
#         submitted = _count_between(post_f, m_start, m_end, where, vals)
#         approved  = _count_between(appr_f, m_start, m_end, where, vals)
#         sent      = _count_between(sent_f, m_start, m_end, where, vals)
#         signed    = _count_between(sign_f, m_start, m_end, where, vals)
#         converted = _count_between(conv_f, m_start, m_end, where, vals)
#         installed = _count_between(inst_f, m_start, m_end, where, vals)

#         # rejected (based on workflow_state)
#         sqlr = f"""SELECT COUNT(name) FROM `tabATM Leads`
#                    WHERE {' AND '.join(where)}
#                    AND workflow_state='Rejected'
#                    AND {post_f} BETWEEN %s AND %s"""
#         rejected = frappe.db.sql(sqlr, vals + [str(m_start), str(m_end)])[0][0]

#         rows.append({
#             "month": ym,
#             "submitted": submitted,
#             "approved": approved,
#             "agreement_sent": sent,
#             "signed": signed,
#             "converted": converted,
#             "installed": installed,
#             "rejected": rejected,
#             "rejection_ratio": pct(rejected, submitted),
#             "sent_to_sign_pct": pct(signed, sent),
#             "sign_to_convert_pct": pct(converted, signed),
#         })

#         chart_labels.append(ym)
#         s_submitted.append(submitted); s_approved.append(approved)
#         s_sent.append(sent); s_signed.append(signed)
#         s_converted.append(converted); s_installed.append(installed)
#         s_rejected.append(rejected)

#         totals["sub"] += submitted; totals["appr"] += approved
#         totals["sent"] += sent; totals["sign"] += signed
#         totals["conv"] += converted; totals["inst"] += installed; totals["rej"] += rejected

#     # ---- Columns ----
#     columns = [
#         {"fieldname": "month", "label": "Month", "fieldtype": "Data", "width": 90},
#         {"fieldname": "submitted", "label": "Submitted", "fieldtype": "Int", "width": 130},
#         {"fieldname": "approved", "label": "Approved", "fieldtype": "Int", "width": 100},
#         {"fieldname": "agreement_sent", "label": "Agreement Sent", "fieldtype": "Int", "width": 130},
#         {"fieldname": "signed", "label": "Signed", "fieldtype": "Int", "width": 100},
#         {"fieldname": "converted", "label": "Converted", "fieldtype": "Int", "width": 110},
#         {"fieldname": "installed", "label": "Installed", "fieldtype": "Int", "width": 110},
#         {"fieldname": "rejected", "label": "Rejected", "fieldtype": "Int", "width": 100},
#         {"fieldname": "rejection_ratio", "label": "Rejection %", "fieldtype": "Percent", "width": 110},
#         {"fieldname": "sent_to_sign_pct", "label": "Agreement Sent → Signed %", "fieldtype": "Percent", "width": 190},
#         {"fieldname": "sign_to_convert_pct", "label": "Signed → Converted %", "fieldtype": "Percent", "width": 190},
#     ]

#     # ---- Chart ----
#     chart = {
#         "type": "bar",
#         "data": {
#             "labels": chart_labels,
#             "datasets": [
#                 {"name": "Submitted", "values": s_submitted},
#                 {"name": "Approved", "values": s_approved},
#                 {"name": "Agreement Sent", "values": s_sent},
#                 {"name": "Signed", "values": s_signed},
#                 {"name": "Converted", "values": s_converted},
#                 {"name": "Installed", "values": s_installed},
#                 {"name": "Rejected", "values": s_rejected},
#             ],
#         },
#         "colors": ["#334155", "#16a34a", "#005c08", "#0ea5e9", "#f59e0b", "#a855f7", "#ef4444"],
#     }

#     # ---- Summary ----
#     report_summary = [
#         {"label": "Submitted", "value": totals["sub"], "indicator": "blue"},
#         {"label": "Approved", "value": totals["appr"], "indicator": "green"},
#         {"label": "Agreement Sent", "value": totals["sent"], "indicator": "green"},
#         {"label": "Signed", "value": totals["sign"], "indicator": "green"},
#         {"label": "Converted", "value": totals["conv"], "indicator": "green"},
#         {"label": "Installed", "value": totals["inst"], "indicator": "green"},
#         {"label": "Rejected", "value": totals["rej"], "indicator": "red"},
#     ]

#     message = (
#         f"Window: <b>{from_date.strftime('%d-%m-%Y')}</b> → <b>{to_date.strftime('%d-%m-%Y')}</b>. "
#         "All counts based on <i>post_date</i>; rejection included."
#     )

#     return columns, rows, message, chart, report_summary

# # -*- coding: utf-8 -*-
# import frappe
# from datetime import date, datetime
# from calendar import monthrange
# from typing import List, Tuple, Dict, Any, Optional

# # ---------- Utilities ----------
# def _parse_date(s: Optional[str]) -> Optional[date]:
#     if not s:
#         return None
#     return datetime.strptime(s, "%Y-%m-%d").date()

# def _month_start(d: date) -> date:
#     return d.replace(day=1)

# def _month_end(d: date) -> date:
#     return date(d.year, d.month, monthrange(d.year, d.month)[1])

# def _iter_months(from_dt: date, to_dt: date) -> List[Tuple[str, date, date]]:
#     """Yield (YYYY-MM, start, end) for each month overlapping [from_dt, to_dt]."""
#     cur = _month_start(from_dt)
#     last = _month_start(to_dt)
#     out = []
#     while cur <= last:
#         out.append((f"{cur.year}-{cur.month:02d}", cur, _month_end(cur)))
#         cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
#     return out

# def _count_between(col: str, start: date, end: date, where: List[str], vals: List[Any]) -> int:
#     """Count rows between dates on given column"""
#     if not col:
#         return 0
#     w = where + [f"{col} BETWEEN %s AND %s"]
#     v = vals + [str(start), str(end)]
#     return frappe.db.sql(f"SELECT COUNT(*) FROM `tabATM Leads` WHERE {' AND '.join(w)}", v)[0][0]

# def _count_rejected(start: date, end: date, where: List[str], vals: List[Any]) -> int:
#     """Count rejected leads (workflow_state='Rejected')"""
#     w = where + ["LOWER(workflow_state)='rejected'", "post_date BETWEEN %s AND %s"]
#     v = vals + [str(start), str(end)]
#     return frappe.db.sql(f"SELECT COUNT(*) FROM `tabATM Leads` WHERE {' AND '.join(w)}", v)[0][0]

# # ---------- Report ----------
# def execute(filters: Optional[Dict[str, Any]] = None):
#     """
#     Script Report: ATM Leads Funnel (monthly)
#     Uses post_date as baseline (Submitted).
#     Adds Rejected and Rejection Ratio.
#     """
#     filters = filters or {}
#     today = date.today()
#     from_date = _parse_date(filters.get("from_date")) or date(today.year - 1, today.month, 1)
#     to_date   = _parse_date(filters.get("to_date")) or today
#     company         = filters.get("company")
#     executive_name  = filters.get("executive_name")

#     # Field mapping from DocType
#     post_f  = "post_date"
#     appr_f  = "approve_date" if frappe.db.has_column("ATM Leads", "approve_date") else None
#     sent_f  = "agreement_sent_date" if frappe.db.has_column("ATM Leads", "agreement_sent_date") else None
#     sign_f  = "sign_date" if frappe.db.has_column("ATM Leads", "sign_date") else None
#     conv_f  = "convert_date" if frappe.db.has_column("ATM Leads", "convert_date") else None
#     inst_f  = "install_date" if frappe.db.has_column("ATM Leads", "install_date") else None

#     # base filters
#     where = ["IFNULL(workflow_state,'') <> 'Draft'", "docstatus < 2"]
#     vals: List[Any] = []
#     if company:
#         where.append("company = %s")
#         vals.append(company)
#     if executive_name:
#         where.append("executive_name = %s")
#         vals.append(executive_name)

#     # roll through months
#     months = _iter_months(from_date, to_date)
#     rows, chart_labels = [], []
#     series_created, series_approved, series_sent, series_signed, series_converted, series_installed, series_rejected = [], [], [], [], [], [], []

#     totals = dict(created=0, approved=0, sent=0, signed=0, converted=0, installed=0, rejected=0)

#     for ym, m_start, m_end in months:
#         created  = _count_between(post_f, m_start, m_end, where, vals)
#         approved = _count_between(appr_f, m_start, m_end, where, vals)
#         sent     = _count_between(sent_f, m_start, m_end, where, vals)
#         signed   = _count_between(sign_f, m_start, m_end, where, vals)
#         converted= _count_between(conv_f, m_start, m_end, where, vals)
#         installed= _count_between(inst_f, m_start, m_end, where, vals)
#         rejected = _count_rejected(m_start, m_end, where, vals)

#         def pct(n, d): return round((n/d)*100, 2) if d else 0.0

#         row = {
#             "month": ym,
#             "submitted": created,
#             "approved": approved,
#             "agreement_sent": sent,
#             "signed": signed,
#             "converted": converted,
#             "installed": installed,
#             "rejected": rejected,
#             "rejection_ratio": pct(rejected, created),
#             "submitted_to_approved": pct(approved, created),
#             "approved_to_sent": pct(sent, approved),
#             "sent_to_signed": pct(signed, sent),
#             "signed_to_converted": pct(converted, signed),
#             "converted_to_installed": pct(installed, converted),
#         }
#         rows.append(row)
#         chart_labels.append(ym)
#         series_created.append(created)
#         series_approved.append(approved)
#         series_sent.append(sent)
#         series_signed.append(signed)
#         series_converted.append(converted)
#         series_installed.append(installed)
#         series_rejected.append(rejected)

#         for k,v in [("created",created),("approved",approved),("sent",sent),
#                     ("signed",signed),("converted",converted),("installed",installed),("rejected",rejected)]:
#             totals[k]+=v

#     # columns
#     columns = [
#         {"fieldname":"month","label":"Month","fieldtype":"Data","width":90},
#         {"fieldname":"submitted","label":"Submitted (post_date)","fieldtype":"Int","width":140},
#         {"fieldname":"approved","label":"Approved","fieldtype":"Int","width":120},
#         {"fieldname":"agreement_sent","label":"Agreement Sent","fieldtype":"Int","width":140},
#         {"fieldname":"signed","label":"Signed","fieldtype":"Int","width":100},
#         {"fieldname":"converted","label":"Converted","fieldtype":"Int","width":110},
#         {"fieldname":"installed","label":"Installed","fieldtype":"Int","width":110},
#         {"fieldname":"rejected","label":"Rejected","fieldtype":"Int","width":110},
#         {"fieldname":"rejection_ratio","label":"Rejection %","fieldtype":"Percent","width":110},

#         {"fieldname":"submitted_to_approved","label":"Submitted → Approved %","fieldtype":"Percent","width":160},
#         {"fieldname":"approved_to_sent","label":"Approved → Agreement Sent %","fieldtype":"Percent","width":190},
#         {"fieldname":"sent_to_signed","label":"Agreement Sent → Signed %","fieldtype":"Percent","width":190},
#         {"fieldname":"signed_to_converted","label":"Signed → Converted %","fieldtype":"Percent","width":170},
#         {"fieldname":"converted_to_installed","label":"Converted → Installed %","fieldtype":"Percent","width":185},
#     ]

#     # chart
#     chart = {
#         "type": "bar",
#         "data": {
#             "labels": chart_labels,
#             "datasets": [
#                 {"name": "Submitted", "values": series_created},
#                 {"name": "Approved", "values": series_approved},
#                 {"name": "Agreement Sent", "values": series_sent},
#                 {"name": "Signed", "values": series_signed},
#                 {"name": "Converted", "values": series_converted},
#                 {"name": "Installed", "values": series_installed},
#                 {"name": "Rejected", "values": series_rejected},
#             ]
#         },
#         "colors": [
#             "#334155", "#16a34a", "#005c08", "#0ea5e9", "#f59e0b", "#a855f7", "#dc2626"
#         ],
#     }

#     report_summary = [
#         {"label": "Submitted (post_date)", "value": totals["created"], "indicator": "blue"},
#         {"label": "Approved", "value": totals["approved"], "indicator": "green"},
#         {"label": "Agreement Sent", "value": totals["sent"], "indicator": "green"},
#         {"label": "Signed", "value": totals["signed"], "indicator": "green"},
#         {"label": "Converted", "value": totals["converted"], "indicator": "green"},
#         {"label": "Installed", "value": totals["installed"], "indicator": "green"},
#         {"label": "Rejected", "value": totals["rejected"], "indicator": "red"},
#         {"label": "Rejection Ratio (%)", "value": f"{round((totals['rejected']/totals['created'])*100,2) if totals['created'] else 0}%", "indicator": "red"},
#     ]

#     msg = f"Window: <b>{from_date.strftime('%d-%m-%Y')}</b> → <b>{to_date.strftime('%d-%m-%Y')}</b>. " \
#           f"All counts based on <i>post_date</i> (Submitted). Drafts excluded."

#     return columns, rows, msg, chart, report_summary

# # # -*- coding: utf-8 -*-
# # import frappe
# # from datetime import date, datetime
# # from calendar import monthrange
# # from typing import List, Tuple, Dict, Any, Optional

# # # ---------- Utilities ----------
# # def _parse_date(s: Optional[str]) -> Optional[date]:
# #     if not s:
# #         return None
# #     return datetime.strptime(s, "%Y-%m-%d").date()

# # def _month_start(d: date) -> date:
# #     return d.replace(day=1)

# # def _month_end(d: date) -> date:
# #     return date(d.year, d.month, monthrange(d.year, d.month)[1])

# # def _iter_months(from_dt: date, to_dt: date) -> List[Tuple[str, date, date]]:
# #     """Yield (YYYY-MM, start, end) for each month overlapping [from_dt, to_dt]."""
# #     cur = _month_start(from_dt)
# #     last = _month_start(to_dt)
# #     out = []
# #     while cur <= last:
# #         out.append((f"{cur.year}-{cur.month:02d}", cur, _month_end(cur)))
# #         # next month
# #         if cur.month == 12:
# #             cur = date(cur.year + 1, 1, 1)
# #         else:
# #             cur = date(cur.year, cur.month + 1, 1)
# #     return out

# # def _has(col: str) -> bool:
# #     return frappe.db.has_column("ATM Leads", col)

# # def _count_between(col: str, start: date, end: date, extra_where: List[str], extra_vals: List[Any]) -> int:
# #     """Count leads where date column between start and end"""
# #     if not col:
# #         return 0
# #     where = extra_where + [f"{col} BETWEEN %s AND %s"]
# #     vals = extra_vals + [str(start), str(end)]
# #     return frappe.db.sql(
# #         f"SELECT COUNT(name) FROM `tabATM Leads` WHERE {' AND '.join(where)}",
# #         vals,
# #     )[0][0]

# # # ---------- Report ----------
# # def execute(filters: Optional[Dict[str, Any]] = None):
# #     """
# #     Script Report: ATM Leads Funnel (monthly)
# #     Uses post_date as baseline (Created = Submitted).
# #     Excludes Draft leads.
# #     """
# #     filters = filters or {}

# #     today = date.today()
# #     from_date = _parse_date(filters.get("from_date")) or date(today.year - 1, today.month, 1)
# #     to_date   = _parse_date(filters.get("to_date")) or today
# #     company         = filters.get("company")
# #     executive_name  = filters.get("executive_name")

# #     # field mapping from your Doctype
# #     post_f  = "post_date"
# #     appr_f  = "approve_date" if _has("approve_date") else None
# #     sent_f  = "agreement_sent_date" if _has("agreement_sent_date") else None
# #     sign_f  = "sign_date" if _has("sign_date") else None
# #     conv_f  = "convert_date" if _has("convert_date") else None
# #     inst_f  = "install_date" if _has("install_date") else None

# #     # base filters
# #     where_base = ["IFNULL(workflow_state,'') <> 'Draft'", "docstatus < 2"]
# #     vals_base: List[Any] = []
# #     if company:
# #         where_base.append("company = %s")
# #         vals_base.append(company)
# #     if executive_name:
# #         where_base.append("executive_name = %s")
# #         vals_base.append(executive_name)

# #     months = _iter_months(from_date, to_date)
# #     rows = []
# #     chart_labels = []
# #     series_created, series_approved, series_sent, series_signed, series_converted, series_installed = [], [], [], [], [], []

# #     totals = dict(created=0, approved=0, sent=0, signed=0, converted=0, installed=0)

# #     for ym, m_start, m_end in months:
# #         created  = _count_between(post_f, m_start, m_end, where_base, vals_base)
# #         approved = _count_between(appr_f, m_start, m_end, where_base, vals_base)
# #         sent     = _count_between(sent_f, m_start, m_end, where_base, vals_base)
# #         signed   = _count_between(sign_f, m_start, m_end, where_base, vals_base)
# #         converted= _count_between(conv_f, m_start, m_end, where_base, vals_base)
# #         installed= _count_between(inst_f, m_start, m_end, where_base, vals_base)

# #         def pct(n, d): return round((n/d)*100, 2) if d else 0.0

# #         row = {
# #             "month": ym,
# #             "created": created,
# #             "approved": approved,
# #             "agreement_sent": sent,
# #             "signed": signed,
# #             "converted": converted,
# #             "installed": installed,
# #             "created_to_approved": pct(approved, created),
# #             "approved_to_sent": pct(sent, approved),
# #             "sent_to_signed": pct(signed, sent),
# #             "signed_to_converted": pct(converted, signed),
# #             "converted_to_installed": pct(installed, converted),
# #         }
# #         rows.append(row)

# #         chart_labels.append(ym)
# #         series_created.append(created)
# #         series_approved.append(approved)
# #         series_sent.append(sent)
# #         series_signed.append(signed)
# #         series_converted.append(converted)
# #         series_installed.append(installed)

# #         totals["created"]  += created
# #         totals["approved"] += approved
# #         totals["sent"]     += sent
# #         totals["signed"]   += signed
# #         totals["converted"]+= converted
# #         totals["installed"]+= installed

# #     # columns
# #     columns = [
# #         {"fieldname":"month","label":"Month","fieldtype":"Data","width":90},
# #         {"fieldname":"created","label":"Submitted (post_date)","fieldtype":"Int","width":140},
# #         {"fieldname":"approved","label":"Approved","fieldtype":"Int","width":120},
# #         {"fieldname":"agreement_sent","label":"Agreement Sent","fieldtype":"Int","width":140},
# #         {"fieldname":"signed","label":"Signed","fieldtype":"Int","width":100},
# #         {"fieldname":"converted","label":"Converted","fieldtype":"Int","width":110},
# #         {"fieldname":"installed","label":"Installed","fieldtype":"Int","width":110},

# #         {"fieldname":"created_to_approved","label":"Submitted → Approved %","fieldtype":"Percent","width":160},
# #         {"fieldname":"approved_to_sent","label":"Approved → Agreement Sent %","fieldtype":"Percent","width":190},
# #         {"fieldname":"sent_to_signed","label":"Agreement Sent → Signed %","fieldtype":"Percent","width":190},
# #         {"fieldname":"signed_to_converted","label":"Signed → Converted %","fieldtype":"Percent","width":170},
# #         {"fieldname":"converted_to_installed","label":"Converted → Installed %","fieldtype":"Percent","width":185},
# #     ]

# #     # chart
# #     chart = {
# #         "type": "bar",
# #         "data": {
# #             "labels": chart_labels,
# #             "datasets": [
# #                 {"name": "Submitted (post_date)", "values": series_created},
# #                 {"name": "Approved", "values": series_approved},
# #                 {"name": "Agreement Sent", "values": series_sent},
# #                 {"name": "Signed", "values": series_signed},
# #                 {"name": "Converted", "values": series_converted},
# #                 {"name": "Installed", "values": series_installed},
# #             ]
# #         },
# #         "colors": ["#334155", "#16a34a", "#005c08", "#0ea5e9", "#f59e0b", "#a855f7"]
# #     }

# #     # summary
# #     report_summary = [
# #         {"label": "Submitted (post_date)", "value": totals["created"], "indicator": "blue"},
# #         {"label": "Approved", "value": totals["approved"], "indicator": "green"},
# #         {"label": "Agreement Sent", "value": totals["sent"], "indicator": "green"},
# #         {"label": "Signed", "value": totals["signed"], "indicator": "green"},
# #         {"label": "Converted", "value": totals["converted"], "indicator": "green"},
# #         {"label": "Installed", "value": totals["installed"], "indicator": "green"},
# #     ]

# #     # message
# #     msg = f"Window: <b>{from_date.strftime('%d-%m-%Y')}</b> → <b>{to_date.strftime('%d-%m-%Y')}</b>. " \
# #           f"Counts based only on <i>post_date</i> (Submitted). All Drafts excluded."

# #     return columns, rows, msg, chart, report_summary
