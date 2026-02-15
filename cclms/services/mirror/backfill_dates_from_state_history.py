import frappe
from frappe.utils import get_datetime

# states -> Operator Deal date fields (same as your mapping)
MILESTONE_STATES = {
    "submitted_date": {"Submitted", "Pending"},
    "approved_date": {"Approved"},
    "rejected_date": {"Rejected", "Signed Rejected", "Not Qualified"},
    "needs_reanalysis_date": {"Needs Reanalysis"},
    "agreement_sent_date": {"Agreement Sent", "Requested for Agreement Sent", "Pending Sign"},
    "signed_date": {"Signed", "Resigned"},
    "converted_date": {"Converted"},
    "installed_date": {"Installed", "installed/Removed", "Removed"},
    "cancelled_date": {"Cancelled", "Hide", "Not Interested"},
    "disputed_date": {"Disputed", "Re Approval"},
}

def _first_dt_from_history(lead_name: str, states: set[str]):
    if not lead_name:
        return None

    rows = frappe.db.sql(
        """
        SELECT to_state, change_datetime, change_date
        FROM `tabATM Lead State History`
        WHERE parent=%s
        ORDER BY COALESCE(change_datetime, change_date) ASC
        """,
        (lead_name,),
        as_dict=True,
    )

    best = None
    for r in rows:
        st = (r.get("to_state") or "").strip()
        if st not in states:
            continue

        dt = r.get("change_datetime") or r.get("change_date")
        if not dt:
            continue

        dt = get_datetime(dt)
        if best is None or dt < best:
            best = dt

    return best

def run(limit: int = 0, commit_every: int = 200, overwrite: int = 0):
    frappe.flags.maintenance_mode = True
    """
    Fill Operator Deal milestone date fields from ATM Lead State History.

    overwrite=0 -> only fill blanks
    overwrite=1 -> overwrite existing values from history
    """
    
    overwrite = bool(int(overwrite))

    deals = frappe.get_all(
        "Operator Deal",
        fields=["name", "source_atm_lead"],
        limit=limit or None,
    )

    updated = 0
    skipped = 0
    missing_lead = 0

    for i, d in enumerate(deals, start=1):
        deal = frappe.get_doc("Operator Deal", d.name)

        lead_name = (deal.source_atm_lead or "").strip()
        if not lead_name:
            missing_lead += 1
            skipped += 1
            continue

        if not frappe.db.exists("ATM Leads", lead_name):
            missing_lead += 1
            skipped += 1
            continue

        changed = False

        for fieldname, states in MILESTONE_STATES.items():
            if (not overwrite) and deal.get(fieldname):
                continue

            dt = _first_dt_from_history(lead_name, states)
            if dt and deal.get(fieldname) != dt:
                deal.set(fieldname, dt)
                changed = True

        if changed:
            deal.flags.skip_strict_duplicate_validation = True
            deal.save(ignore_permissions=True)
            updated += 1
        else:
            skipped += 1

        if commit_every and i % int(commit_every) == 0:
            frappe.db.commit()

    frappe.db.commit()

    return {
        "processed": len(deals),
        "updated": updated,
        "skipped": skipped,
        "missing_lead": missing_lead,
        "overwrite": int(overwrite),
    }
