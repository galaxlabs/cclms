import frappe

__all__ = ("get_state_counts_by_executive",)  # optional but nice

def _safe_col(df: str) -> str:
    # Use given column if it exists; otherwise fall back to 'creation'
    return df if frappe.db.has_column("ATM Leads", df) else "creation"

def _where(parts):
    return "WHERE " + " AND ".join(parts) if parts else ""

@frappe.whitelist(allow_guest=True)
def get_state_counts_by_executive(
    start_date=None,
    end_date=None,
    company=None,
    executive_name=None,
    date_field="post_date",
    include_states=None,   # optional CSV list to force series order
):
    """
    Snapshot counts of current workflow_state per executive, windowed by date_field (default: post_date).
    Draft is excluded to match card logic.
    Returns: { categories: [executive...], series: [{name:state, data:[counts...] }], states:[...] }
    """
    post = _safe_col(date_field)

    conds, vals = [], []
    if start_date and end_date:
        conds.append(f"{post} BETWEEN %s AND %s")
        vals.extend([start_date, end_date])
    if company:
        conds.append("company = %s")
        vals.append(company)
    if executive_name:
        conds.append("executive_name = %s")
        vals.append(executive_name)

    # Exclude Draft to mirror the cards
    conds.append("IFNULL(workflow_state,'') <> 'Draft'")

    rows = frappe.db.sql(
        f"""
        SELECT
          COALESCE(executive_name, '-') AS executive_name,
          IFNULL(workflow_state, 'Unknown') AS state,
          COUNT(name) AS total
        FROM `tabATM Leads`
        {_where(conds)}
        GROUP BY executive_name, state
        """,
        values=vals,
        as_dict=True,
    )

    # Build category (executives) and state lists
    execs = sorted({r["executive_name"] for r in rows})
    default_order = ["Submitted","Approved","Rejected","Agreement Sent","Signed","Converted","Installed","Unknown"]
    states = [s.strip() for s in include_states.split(",")] if include_states else list(default_order)

    # Ensure we include any unexpected states present in data
    seen_states = {r["state"] for r in rows}
    for s in sorted(seen_states):
        if s not in states:
            states.append(s)

    # Create exec x state matrix
    counts = {e: {s: 0 for s in states} for e in execs}
    for r in rows:
        counts[r["executive_name"]][r["state"]] = int(r["total"])

    # Sort executives by total volume (desc)
    execs.sort(key=lambda e: sum(counts[e].values()), reverse=True)

    series = [{"name": s, "data": [counts[e][s] for e in execs]} for s in states]
    return {"categories": execs, "series": series, "states": states}
