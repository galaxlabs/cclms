import frappe
from frappe.utils import get_datetime

# same mapping as your mirror
MILESTONE_STATES = {
    "approved_date": {"Approved"},
    "rejected_date": {"Rejected", "Signed Rejected", "Not Qualified"},
    "agreement_sent_date": {"Agreement Sent", "Requested for Agreement Sent", "Pending Sign"},
    "signed_date": {"Signed", "Resigned"},
    "converted_date": {"Converted"},
    "installed_date": {"Installed", "installed/Removed"},
    "cancelled_date": {"Cancelled", "Hide", "Not Interested"},
    "needs_reanalysis_date": {"Needs Reanalysis"},
    "disputed_date": {"Disputed", "Re Approval"},
}

DATE_FIELDS = list(MILESTONE_STATES.keys())

def _first_dt_from_history(lead, states):
    best = None
    for r in (lead.state_history or []):
        st = (r.to_state or "").strip()
        if st in states:
            dt = r.change_datetime or r.change_date
            if not dt:
                continue
            dt = get_datetime(dt)
            if best is None or dt < best:
                best = dt
    return best

def run(limit: int = 0, commit_every: int = 200):
    deals = frappe.get_all(
        "Operator Deal",
        fields=["name", "source_atm_lead"],
        limit=limit or None
    )

    updated = 0
    skipped = 0

    for i, d in enumerate(deals, start=1):
        if not d.source_atm_lead or not frappe.db.exists("ATM Leads", d.source_atm_lead):
            skipped += 1
            continue

        lead = frappe.get_doc("ATM Leads", d.source_atm_lead)
        deal = frappe.get_doc("Operator Deal", d.name)

        changed = False
        for f, states in MILESTONE_STATES.items():
            dt = _first_dt_from_history(lead, states)
            # FORCE overwrite: if history has dt, set it (even if deal already has value)
            if dt:
                if deal.get(f) != dt:
                    deal.set(f, dt)
                    changed = True

        if changed:
            deal.save(ignore_permissions=True)
            updated += 1

        if commit_every and i % int(commit_every) == 0:
            frappe.db.commit()

    frappe.db.commit()
    return {"processed": len(deals), "updated": updated, "skipped": skipped}
