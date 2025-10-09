# Copyright (c) 2025, Galaxy and contributors
# For license information, please see license.txt

# -*- coding: utf-8 -*-
import frappe
from datetime import datetime
from frappe.utils import getdate, flt

# Helper: safe count with date field window + optional company/executive
def _count(tab, date_field, start, end, company=None, exec_name=None, extra_where="", extra_args=()):
    where = [f"`{date_field}` BETWEEN %s AND %s"]
    args = [start, end]

    if company:
        where.append("`company` = %s")
        args.append(company)

    if exec_name:
        where.append("`executive_name` = %s")
        args.append(exec_name)

    if extra_where:
        where.append(extra_where)
        args += list(extra_args)

    sql = f"SELECT COUNT(*) FROM `tab{tab}` WHERE " + " AND ".join(where)
    return frappe.db.sql(sql, tuple(args))[0][0]

def _lag_days(tab, from_field, to_field, start, end, company=None, exec_name=None):
    # measure lag for records that REACH to_field in window
    where = [f"`{to_field}` BETWEEN %s AND %s",
             f"`{from_field}` IS NOT NULL",
             f"`{to_field}` IS NOT NULL"]
    args = [start, end]
    if company:
        where.append("`company`=%s"); args.append(company)
    if exec_name:
        where.append("`executive_name`=%s"); args.append(exec_name)

    sql = f"""
    SELECT DATEDIFF(`{to_field}`, `{from_field}`) AS d
    FROM `tabATM Leads`
    WHERE {" AND ".join(where)}
    """
    rows = [r[0] for r in frappe.db.sql(sql, tuple(args))]
    if not rows:
        return {"n":0, "median":None, "buckets":dict(d0_7=0,d8_30=0,d31_60=0,d61_90=0,d90p=0)}
    s = sorted([int(x) for x in rows if x is not None])
    n = len(s); med = s[n//2] if n%2 else round((s[n//2-1]+s[n//2])/2, 1)
    B = dict(d0_7=0,d8_30=0,d31_60=0,d61_90=0,d90p=0)
    for v in s:
        if v<=7: B["d0_7"]+=1
        elif v<=30: B["d8_30"]+=1
        elif v<=60: B["d31_60"]+=1
        elif v<=90: B["d61_90"]+=1
        else: B["d90p"]+=1
    return {"n": n, "median": med, "buckets": B}

def _pct(n, d):
    return round((flt(n)/flt(d))*100, 2) if flt(d) > 0 else 0.0

def get_columns():
    return [
        {"label":"From", "fieldname":"from_state", "fieldtype":"Data", "width":140},
        {"label":"To", "fieldname":"to_state", "fieldtype":"Data", "width":160},
        {"label":"Date Field", "fieldname":"date_field", "fieldtype":"Data", "width":160},
        {"label":"Count", "fieldname":"count", "fieldtype":"Int", "width":90},
        {"label":"Conversion %", "fieldname":"conversion", "fieldtype":"Data", "width":110},
    ]

def _states():
    return [
        ("Created","post_date"),
        ("Approved","approve_date"),
        ("Agreement Sent","agreement_sent_date"),
        ("Signed","sign_date"),
        ("Converted","convert_date"),
        ("Installed","install_date"),
    ]

def _agent_rows(start, end, company=None):
    # summary by executive over the window (post_date baseline + stage counts by their own dates)
    agents = frappe.get_all("Sales Agent", fields=["full_name as executive_name", "kpi_minimum", "kpi_maximum"])
    out = []
    for a in agents:
        total_post = _count("ATM Leads", "post_date", start, end, company, a["executive_name"])
        appr = _count("ATM Leads", "approve_date", start, end, company, a["executive_name"])
        sent = _count("ATM Leads", "agreement_sent_date", start, end, company, a["executive_name"])
        sign = _count("ATM Leads", "sign_date", start, end, company, a["executive_name"])
        conv = _count("ATM Leads", "convert_date", start, end, company, a["executive_name"])
        rej = frappe.db.count("ATM Leads", filters={
            "post_date": ["between", [start, end]],
            "executive_name": a["executive_name"],
            "company": company} if company else {
            "post_date": ["between", [start, end]],
            "executive_name": a["executive_name"]
        }, cache=False, debug=False)  # we’ll compute rejection via workflow_state below (better if you add rejected_date)
        # Better rejection via workflow_state:
        rej = frappe.db.sql("""SELECT COUNT(*) FROM `tabATM Leads`
                               WHERE `post_date` BETWEEN %s AND %s
                               AND `executive_name`=%s {company}
                               AND LOWER(`workflow_state`)='rejected'"""
                            .format(company="AND `company`=%s" if company else ""),
                            (start, end, a["executive_name"]) + ((company,) if company else tuple()))[0][0]

        out.append(dict(
            executive_name=a["executive_name"], total_post=total_post, approved=appr,
            agreement_sent=sent, signed=sign, converted=conv,
            rejected=rej,
            kpi_min=a.get("kpi_minimum"), kpi_max=a.get("kpi_maximum"),
            signed_plus_converted=sign+conv,
            sign_vs_total=_pct(sign, total_post),
            conv_vs_total=_pct(conv, total_post),
        ))
    # keep only those with any activity
    return [r for r in out if any([r["total_post"],r["approved"],r["agreement_sent"],r["signed"],r["converted"]])]

def _quality_gaps(start, end, company=None, exec_name=None):
    where = ["`post_date` BETWEEN %s AND %s"]; args=[start,end]
    if company: where.append("`company`=%s"); args.append(company)
    if exec_name: where.append("`executive_name`=%s"); args.append(exec_name)
    base = " FROM `tabATM Leads` WHERE " + " AND ".join(where)
    total = frappe.db.sql("SELECT COUNT(*)"+base, tuple(args))[0][0]
    missing_addr = frappe.db.sql(
        "SELECT COUNT(*)"+base+" AND (COALESCE(`city`,'')='' OR COALESCE(`state`,'')='' OR COALESCE(`zippostal_code`,'')='')",
        tuple(args)
    )[0][0]
    missing_geo = frappe.db.sql(
        "SELECT COUNT(*)"+base+" AND (COALESCE(`latitude`,'')='' OR COALESCE(`longitude`,'')='')",
        tuple(args)
    )[0][0]
    return dict(total=total, missing_addr=missing_addr, missing_geo=missing_geo,
                addr_pct=_pct(missing_addr,total), geo_pct=_pct(missing_geo,total))

def execute(filters=None):
    f = filters or {}
    start = (f.get("from") or f.get("start_date"))
    end   = (f.get("to")   or f.get("end_date"))
    if not (start and end):
        # default: current month
        today = getdate()
        start = today.replace(day=1).isoformat()
        end = today.isoformat()
    company = f.get("company") or None
    exec_name = f.get("executive_name") or None

    # Stage counts by destination dates
    created   = _count("ATM Leads", "post_date", start, end, company, exec_name)
    approved  = _count("ATM Leads", "approve_date", start, end, company, exec_name)
    sent      = _count("ATM Leads", "agreement_sent_date", start, end, company, exec_name)
    signed    = _count("ATM Leads", "sign_date", start, end, company, exec_name)
    converted = _count("ATM Leads", "convert_date", start, end, company, exec_name)
    installed = _count("ATM Leads", "install_date", start, end, company, exec_name)

    # Conversion%
    c_appr = _pct(approved, created)
    c_sent = _pct(sent, approved)
    c_sign = _pct(signed, sent)
    c_conv = _pct(converted, signed)
    c_inst = _pct(installed, converted)

    # Lag analytics
    lag_ca = _lag_days("ATM Leads", "post_date", "approve_date", start, end, company, exec_name)
    lag_as = _lag_days("ATM Leads", "approve_date", "agreement_sent_date", start, end, company, exec_name)
    lag_ss = _lag_days("ATM Leads", "agreement_sent_date", "sign_date", start, end, company, exec_name)
    lag_sc = _lag_days("ATM Leads", "sign_date", "convert_date", start, end, company, exec_name)

    # Agent overview
    agent_rows = _agent_rows(start, end, company)

    # Data quality
    q = _quality_gaps(start, end, company, exec_name)

    # Table rows like your current “From → To”
    columns = get_columns()
    rows = [
        dict(from_state="Draft", to_state="Submitted", date_field="post_date", count=created, conversion=f"{_pct(created, created) if created else 0}%"),
        dict(from_state="Approved", to_state="Agreement Sent", date_field="agreement_sent_date", count=sent, conversion=f"{c_sent}%"),
        dict(from_state="Agreement Sent", to_state="Signed", date_field="sign_date", count=signed, conversion=f"{c_sign}%"),
        dict(from_state="Signed", to_state="Converted", date_field="convert_date", count=converted, conversion=f"{c_conv}%"),
    ]

    # Chart (counts + conversion%)
    labels = ["Submitted","Agreement Sent","Signed","Converted"]
    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "Counts", "values": [created, sent, signed, converted]},
                {"name": "Conversion %", "values": [c_appr, c_sent, c_sign, c_conv]}
            ]
        },
        "type": "bar",
    }

    # Summary tiles
    report_summary = [
        {"label":"Created (post_date)", "value": created, "datatype":"Int"},
        {"label":"Approved", "value": approved, "datatype":"Int"},
        {"label":"Agreement Sent", "value": sent, "datatype":"Int"},
        {"label":"Signed", "value": signed, "datatype":"Int"},
        {"label":"Converted", "value": converted, "datatype":"Int"},
    ]

    # Message (window + lag medians + quality)
    msg = f"Window: <b>{start}</b> → <b>{end}</b>. "\
          f"Median days: C→A={lag_ca['median']}, A→Snt={lag_as['median']}, Snt→Sig={lag_ss['median']}, Sig→Conv={lag_sc['median']}. "\
          f"Quality gaps: Missing Address={q['addr_pct']}%, Missing Geo={q['geo_pct']}%."

    return columns, rows, msg, chart, report_summary
