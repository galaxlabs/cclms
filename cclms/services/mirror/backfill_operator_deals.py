import frappe

def run(limit: int = 0):
    from cclms.services.mirror.atm_lead_mirror import upsert_from_atm_lead

    filters = {"workflow_state": ["!=", "Draft"]}
    leads = frappe.get_all("ATM Leads", filters=filters, pluck="name", limit=limit or None)

    ok, fail = 0, 0
    for i, name in enumerate(leads, start=1):
        try:
            lead = frappe.get_doc("ATM Leads", name)
            upsert_from_atm_lead(lead, method="backfill")
            ok += 1
        except Exception:
            fail += 1
            frappe.log_error(title="Operator Deal Backfill Failed", message=frappe.get_traceback())

        # ✅ persist inserts
        if i % 50 == 0:
            frappe.db.commit()

    frappe.db.commit()
    return {"processed": len(leads), "ok": ok, "fail": fail}
