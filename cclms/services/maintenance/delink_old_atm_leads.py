import frappe
from frappe.utils import get_datetime

def run(cutoff_date="2025-08-01", commit_every: int = 500):
    cutoff = get_datetime(cutoff_date)

    rows = frappe.db.sql("""
        SELECT od.name AS deal
        FROM `tabOperator Deal` od
        JOIN `tabATM Leads` l ON l.name = od.source_atm_lead
        WHERE l.creation < %(cutoff)s
    """, {"cutoff": cutoff}, as_dict=True)

    updated = 0
    for i, r in enumerate(rows, start=1):
        frappe.db.set_value("Operator Deal", r.deal, "source_atm_lead", None, update_modified=False)
        updated += 1
        if commit_every and i % commit_every == 0:
            frappe.db.commit()

    frappe.db.commit()
    return {"matched": len(rows), "delinked": updated, "cutoff": cutoff_date}
