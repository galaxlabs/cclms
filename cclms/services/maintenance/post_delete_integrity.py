import frappe
from collections import Counter

def run(commit_every: int = 200):
    reasons = Counter()
    fixed = 0
    checked = 0

    deals = frappe.get_all("Operator Deal", fields=["name", "location", "source_atm_lead"])

    for i, d in enumerate(deals, start=1):
        checked += 1

        # 1) missing location doc
        if d.location and not frappe.db.exists("BTM Location", d.location):
            deal = frappe.get_doc("Operator Deal", d.name)
            deal.flags.skip_strict_duplicate_validation = True

            # safest: keep record but neutralize it
            if hasattr(deal, "status"):
                deal.status = "Cancelled"
            deal.location = None
            deal.save(ignore_permissions=True)

            fixed += 1
            reasons["orphan_location_fixed"] += 1

        # 2) missing source lead (optional)
        if (not d.source_atm_lead) or (d.source_atm_lead and not frappe.db.exists("ATM Leads", d.source_atm_lead)):
            reasons["missing_source_lead"] += 1

        if commit_every and i % int(commit_every) == 0:
            frappe.db.commit()

    frappe.db.commit()

    return {
        "checked": checked,
        "fixed": fixed,
        "reasons": dict(reasons),
    }
