import frappe
from datetime import date
from calendar import monthrange

def _safe_col(df: str) -> str:
    # fallback only if the field truly doesn't exist
    return df if frappe.db.has_column("ATM Leads", df) else "creation"

def _month_window(ym: str | None):
    """ym: 'YYYY-MM'; None -> current month."""
    if not ym:
        today = date.today()
        y, m = today.year, today.month
    else:
        y, m = [int(x) for x in ym.split("-")]
    start = date(y, m, 1)
    end = date(y, m, monthrange(y, m)[1])
    return str(start), str(end)

def _where(clauses):
    return f"WHERE {' AND '.join(clauses)}" if clauses else ""

@frappe.whitelist(allow_guest=True)
def get_monthly_performance(
    month: str | None = None,
    company: str | None = None,
    executive_name: str | None = None,
    # ✅ defaults match your DocType fields (approve_date, agreement_sent_date, sign_date, convert_date)
    post_date_field: str = "post_date",
    approve_date_field: str = "approve_date",
    sent_date_field: str = "agreement_sent_date",
    sign_date_field: str = "sign_date",
    convert_date_field: str = "convert_date",
):
    """Monthly performance using event dates + cohort attribution (post_date)."""

    post_f   = _safe_col(post_date_field)
    appr_f   = _safe_col(approve_date_field)
    sent_f   = _safe_col(sent_date_field)
    sign_f   = _safe_col(sign_date_field)
    conv_f   = _safe_col(convert_date_field)

    m_start, m_end = _month_window(month)

    base_conds, base_vals = [], []
    if company:
        base_conds.append("company = %s"); base_vals.append(company)
    if executive_name:
        base_conds.append("executive_name = %s"); base_vals.append(executive_name)

    # 1) Origin cohort: leads CREATED in month (by post_date), excluding Draft
    conds = base_conds + [f"{post_f} BETWEEN %s AND %s", "IFNULL(workflow_state,'') <> 'Draft'"]
    vals = base_vals + [m_start, m_end]
    total_created = frappe.db.sql(
        f"SELECT COUNT(name) FROM `tabATM Leads` {_where(conds)}",
        values=vals
    )[0][0]

    # helper to count any event by its date column
    def _count_event(col):
        conds2 = base_conds + [f"{col} BETWEEN %s AND %s", "IFNULL(workflow_state,'') <> 'Draft'"]
        vals2 = base_vals + [m_start, m_end]
        return frappe.db.sql(
            f"SELECT COUNT(name) FROM `tabATM Leads` {_where(conds2)}",
            values=vals2
        )[0][0]

    approved_in_month   = _count_event(appr_f)
    sent_in_month       = _count_event(sent_f)
    signed_in_month     = _count_event(sign_f)
    converted_in_month  = _count_event(conv_f)

    # “Signed (incl Converted)” counts both event types inside the month
    signed_plus_converted_in_month = int(signed_in_month or 0) + int(converted_in_month or 0)

    # 2) Same-month vs Carry-in splits
    # Signed
    conds = base_conds + [f"{sign_f} BETWEEN %s AND %s", f"{post_f} BETWEEN %s AND %s", "IFNULL(workflow_state,'') <> 'Draft'"]
    vals = base_vals + [m_start, m_end, m_start, m_end]
    signed_same_month = frappe.db.sql(
        f"SELECT COUNT(name) FROM `tabATM Leads` {_where(conds)}", values=vals
    )[0][0]

    conds = base_conds + [f"{sign_f} BETWEEN %s AND %s", f"{post_f} < %s", "IFNULL(workflow_state,'') <> 'Draft'"]
    vals = base_vals + [m_start, m_end, m_start]
    signed_carry_in = frappe.db.sql(
        f"SELECT COUNT(name) FROM `tabATM Leads` {_where(conds)}", values=vals
    )[0][0]

    # Converted
    conds = base_conds + [f"{conv_f} BETWEEN %s AND %s", f"{post_f} BETWEEN %s AND %s", "IFNULL(workflow_state,'') <> 'Draft'"]
    vals = base_vals + [m_start, m_end, m_start, m_end]
    converted_same_month = frappe.db.sql(
        f"SELECT COUNT(name) FROM `tabATM Leads` {_where(conds)}", values=vals
    )[0][0]

    conds = base_conds + [f"{conv_f} BETWEEN %s AND %s", f"{post_f} < %s", "IFNULL(workflow_state,'') <> 'Draft'"]
    vals = base_vals + [m_start, m_end, m_start]
    converted_carry_in = frappe.db.sql(
        f"SELECT COUNT(name) FROM `tabATM Leads` {_where(conds)}", values=vals
    )[0][0]

    # 3) Lag buckets for signatures (post_date -> sign_date)
    conds = base_conds + [f"{sign_f} BETWEEN %s AND %s", "IFNULL(workflow_state,'') <> 'Draft'"]
    vals = base_vals + [m_start, m_end]
    lag_row = frappe.db.sql(
        f"""
        SELECT
          SUM(CASE WHEN DATEDIFF({sign_f}, {post_f}) BETWEEN 0 AND 7  THEN 1 ELSE 0 END) AS d0_7,
          SUM(CASE WHEN DATEDIFF({sign_f}, {post_f}) BETWEEN 8 AND 30 THEN 1 ELSE 0 END) AS d8_30,
          SUM(CASE WHEN DATEDIFF({sign_f}, {post_f}) BETWEEN 31 AND 60 THEN 1 ELSE 0 END) AS d31_60,
          SUM(CASE WHEN DATEDIFF({sign_f}, {post_f}) BETWEEN 61 AND 90 THEN 1 ELSE 0 END) AS d61_90,
          SUM(CASE WHEN DATEDIFF({sign_f}, {post_f}) > 90 THEN 1 ELSE 0 END) AS d90p
        FROM `tabATM Leads`
        {_where(conds)}
        """,
        values=vals,
        as_dict=True,
    )[0]

    def pct(num, den):
        num, den = int(num or 0), int(den or 0)
        return round((num / den) * 100.0, 1) if den > 0 else 0.0

    ratios = {
        # Signed-only
        "sign_vs_total_pct": pct(signed_in_month, total_created),
        "sign_vs_approved_pct": pct(signed_in_month, approved_in_month),
        "sign_vs_agreement_sent_pct": pct(signed_in_month, sent_in_month),
        # Converted-only
        "converted_vs_total_pct": pct(converted_in_month, total_created),
        "converted_vs_approved_pct": pct(converted_in_month, approved_in_month),
        "converted_vs_agreement_sent_pct": pct(converted_in_month, sent_in_month),
        # Combined
        "signed_plus_converted_vs_total_pct": pct(signed_plus_converted_in_month, total_created),
    }

    return {
        "month_start": m_start, "month_end": m_end,
        "counts": {
            "total_created": total_created,

            "approved_in_month": approved_in_month,
            "agreement_sent_in_month": sent_in_month,

            "signed_in_month": signed_in_month,
            "signed_same_month": signed_same_month,
            "signed_carry_in": signed_carry_in,

            "converted_in_month": converted_in_month,
            "converted_same_month": converted_same_month,
            "converted_carry_in": converted_carry_in,

            "signed_plus_converted_in_month": signed_plus_converted_in_month,
        },
        "lag_buckets": lag_row,
        "ratios": ratios,
    }
