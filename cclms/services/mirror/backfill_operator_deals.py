import frappe
from collections import Counter

def upsert_from_atm_lead(lead, method=None):
    from cclms.services.mirror.operator_deal_sync import sync_atm_lead

    mode = "backfill" if method == "backfill" else "live"
    result = sync_atm_lead(lead, mode=mode, overwrite=False)
    return result.get("deal") if result.get("status") == "ok" else None

def run(limit: int = 0, commit_every: int = 200, stop_on_error: int = 0):
    """
    Backfill Operator Deal from ATM Leads using mirror upsert.

    Args:
        limit (int): 0 means all, otherwise only N leads.
        commit_every (int): commit after this many records.
        stop_on_error (int): 1 to raise on first error, else continue.
    Returns:
        dict: processed/ok/fail/skipped + reason summary
    """
    from cclms.services.mirror.atm_lead_mirror import upsert_from_atm_lead

    filters = {"workflow_state": ["!=", "Draft"]}
    leads = frappe.get_all("ATM Leads", filters=filters, pluck="name", limit=limit or None)

    ok, fail, skipped = 0, 0, 0
    reasons = Counter()

    for i, name in enumerate(leads, start=1):
        sp = f"bf_{i}"
        frappe.db.savepoint(sp)

        try:
            lead = frappe.get_doc("ATM Leads", name)

            res = upsert_from_atm_lead(lead, method="backfill")

            if not res:
                skipped += 1
                reasons["skipped_no_action"] += 1
            else:
                ok += 1

        except Exception as e:
            fail += 1
            frappe.db.rollback(save_point=sp)

            msg = (str(e) or "").lower()
            tb = frappe.get_traceback().lower()

            if "missing address" in tb or "missing address" in msg:
                reasons["missing_address_zip"] += 1
            elif "rejected by an operator" in msg:
                reasons["blocked_location_rejected"] += 1
            elif "signed/installed" in msg:
                reasons["blocked_location_signed_installed"] += 1
            elif "mandatoryerror" in tb:
                reasons["missing_mandatory_fields"] += 1
            elif "duplicate entry" in tb or "duplicateentryerror" in tb:
                reasons["duplicate_record"] += 1
            else:
                reasons["other"] += 1

            frappe.log_error(
                title="Operator Deal Backfill Failed",
                message=f"ATM Lead: {name}\n\n{frappe.get_traceback()}"
            )

            if int(stop_on_error) == 1:
                raise

        if commit_every and i % int(commit_every) == 0:
            frappe.db.commit()

    frappe.db.commit()

    return {
        "processed": len(leads),
        "ok": ok,
        "fail": fail,
        "skipped": skipped,
        "reasons": dict(reasons),
    }
