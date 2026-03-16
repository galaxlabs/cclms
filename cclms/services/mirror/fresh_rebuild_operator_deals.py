import frappe
from collections import Counter
from frappe.utils import get_datetime


def run(
    cutoff_date: str,
    limit: int = 200,
    offset: int = 0,
    commit_every: int = 200,
    stop_on_error: int = 0,
):
    """
    Batch rebuild Operator/BTM Location/Operator Deal from ATM Leads.

    Only processes leads where:
      - workflow_state != Draft
      - AND (creation >= cutoff_date OR modified >= cutoff_date)

    Uses upsert_from_atm_lead(..., method="backfill") so milestone dates are derived from state history.
    """

    if not cutoff_date:
        frappe.throw("cutoff_date is required")

    cutoff_dt = get_datetime(cutoff_date)

    from cclms.services.mirror.atm_lead_mirror import upsert_from_atm_lead

    leads = frappe.get_all(
        "ATM Leads",
        filters={"workflow_state": ["!=", "Draft"]},
        fields=["name", "creation", "modified"],
        order_by="modified asc",
        limit=int(limit),
        start=int(offset),
    )

    ok = 0
    fail = 0
    skipped = 0
    reasons = Counter()

    for i, l in enumerate(leads, start=1):
        creation_dt = get_datetime(l.creation) if l.creation else None
        modified_dt = get_datetime(l.modified) if l.modified else None

        eligible = False
        if creation_dt and creation_dt >= cutoff_dt:
            eligible = True
        if modified_dt and modified_dt >= cutoff_dt:
            eligible = True

        if not eligible:
            skipped += 1
            reasons["skipped_before_cutoff"] += 1
            continue

        sp = f"rb_{offset}_{i}"
        frappe.db.savepoint(sp)

        try:
            lead = frappe.get_doc("ATM Leads", l.name)
            res = upsert_from_atm_lead(lead, method="backfill")

            if res:
                ok += 1
            else:
                skipped += 1
                reasons["skipped_no_action"] += 1

        except Exception:
            fail += 1
            frappe.db.rollback(save_point=sp)

            tb = frappe.get_traceback().lower()
            if "missing address" in tb or "missing address/zip" in tb:
                reasons["missing_address_zip"] += 1
            elif "mandatoryerror" in tb:
                reasons["missing_mandatory_fields"] += 1
            elif "duplicate entry" in tb or "duplicateentryerror" in tb:
                reasons["duplicate_record"] += 1
            else:
                reasons["other"] += 1

            frappe.log_error(
                title="Rebuild Deals Since Cutoff Failed",
                message=f"ATM Lead: {l.name}\n\n{frappe.get_traceback()}",
            )

            if int(stop_on_error) == 1:
                raise

        if commit_every and i % int(commit_every) == 0:
            frappe.db.commit()

    frappe.db.commit()

    next_offset = int(offset) + len(leads)

    return {
        "cutoff_date": cutoff_date,
        "offset": int(offset),
        "processed_in_batch": len(leads),
        "next_offset": next_offset,
        "ok": ok,
        "fail": fail,
        "skipped": skipped,
        "reasons": dict(reasons),
    }
