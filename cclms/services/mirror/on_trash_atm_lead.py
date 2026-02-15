import frappe

def delink_operator_deals(doc, method=None):
    frappe.db.sql("""
        UPDATE `tabOperator Deal`
        SET source_atm_lead = NULL
        WHERE source_atm_lead = %s
    """, (doc.name,))
