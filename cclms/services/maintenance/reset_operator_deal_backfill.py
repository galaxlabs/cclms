import frappe
from frappe.utils import get_datetime

DATE_FIELDS = [
    "submitted_date",
    "approved_date",
    "rejected_date",
    "needs_reanalysis_date",
    "agreement_sent_date",
    "signed_date",
    "converted_date",
    "install_scheduled_date",
    "installed_date",
    "cancelled_date",
    "disputed_date",
]

def run(cutoff_date="2025-08-01", commit_every: int = 500):
    cutoff = get_datetime(cutoff_date)

    deals = frappe.get_all(
        "Operator Deal",
        fields=["name", "creation"],
        filters={"creation": [">=", cutoff]},
        limit=None
    )

    updated = 0
    for i, d in enumerate(deals, start=1):
        values = {f: None for f in DATE_FIELDS}
        values["source_atm_lead"] = None

        frappe.db.set_value("Operator Deal", d.name, values, update_modified=False)
        updated += 1

        if commit_every and i % commit_every == 0:
            frappe.db.commit()

    frappe.db.commit()
    return {"matched": len(deals), "reset": updated, "cutoff": cutoff_date}
