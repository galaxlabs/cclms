import frappe

def _safe_col(df: str) -> str:
    return df if frappe.db.has_column("ATM Leads", df) else "creation"

def _where(parts):
    return "WHERE " + " AND ".join(parts) if parts else ""

@frappe.whitelist(allow_guest=True)
def get_conversions_summary(
    start_date=None, end_date=None,
    company=None, executive_name=None,
    post_date_field="post_date",
    approve_date_field="approve_date",
    sent_date_field="agreement_sent_date",
    sign_date_field="sign_date",
    convert_date_field="convert_date",
):
    """
    Cohort metrics: consider leads whose post_date is within [start_date, end_date].
    Event counts ignore current workflow_state (so Converted still counts toward Signed+Converted).
    """
    post = _safe_col(post_date_field)
    appr = _safe_col(approve_date_field)
    sent = _safe_col(sent_date_field)
    sign = _safe_col(sign_date_field)
    conv = _safe_col(convert_date_field)

    # Base cohort (post_date window)
    base_conds, base_vals = [], []
    if start_date and end_date:
        base_conds.append(f"{post} BETWEEN %s AND %s"); base_vals.extend([start_date, end_date])
    if company:
        base_conds.append("company = %s"); base_vals.append(company)
    if executive_name:
        base_conds.append("executive_name = %s"); base_vals.append(executive_name)

    # total cohort size (keep drafts included to match your 1012 baseline)
    cohort_total = frappe.db.sql(
        f"SELECT COUNT(name) FROM `tabATM Leads` {_where(base_conds)}",
        values=base_vals
    )[0][0]

    # helpers reuse base + extra condition
    def count_with(extra_sql, extra_vals=()):
        conds = list(base_conds) + [extra_sql]
        vals = list(base_vals) + list(extra_vals)
        return frappe.db.sql(
            f"SELECT COUNT(name) FROM `tabATM Leads` {_where(conds)}",
            values=vals
        )[0][0]

    rejected = count_with("IFNULL(workflow_state,'') = 'Rejected'")
    approved = count_with(f"{appr} IS NOT NULL")
    agreement_sent = count_with(f"{sent} IS NOT NULL")
    signed = count_with(f"{sign} IS NOT NULL")
    converted = count_with(f"{conv} IS NOT NULL")
    signed_plus_converted = count_with(f"({sign} IS NOT NULL OR {conv} IS NOT NULL)")

    def pct(n, d): 
        n = int(n or 0); d = int(d or 0)
        return round((n/d)*100.0, 1) if d > 0 else 0.0

    ratios = {
        "rejected_vs_total_pct": pct(rejected, cohort_total),
        "approved_vs_total_pct": pct(approved, cohort_total),
        "agrsent_vs_approved_pct": pct(agreement_sent, approved),
        "signedplus_vs_total_pct": pct(signed_plus_converted, cohort_total),
        "signedplus_vs_approved_pct": pct(signed_plus_converted, approved),
        "signedplus_vs_agrsent_pct": pct(signed_plus_converted, agreement_sent),
    }

    return {
        "cohort_total": int(cohort_total),
        "rejected": int(rejected),
        "approved": int(approved),
        "agreement_sent": int(agreement_sent),
        "signed": int(signed),
        "converted": int(converted),
        "signed_plus_converted": int(signed_plus_converted),
        "ratios": ratios,
    }
