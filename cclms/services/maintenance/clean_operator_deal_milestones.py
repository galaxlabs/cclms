import frappe
from frappe.utils import get_datetime

from cclms.services.mirror.atm_lead_mirror import apply_milestone_dates_from_lead_history

def _fingerprint(address: str, zip_code: str) -> str:
    addr = " ".join((address or "").lower().split())
    z = (zip_code or "").strip()
    return f"{addr}|{z}"

def _find_atm_lead_by_location_and_operator(location_name: str, operator_company: str):
    """
    If Operator Deal has no source_atm_lead, try to find it by:
    - Operator company match (ATM Leads.company)
    - address_fingerprint match (BTM Location vs ATM Leads address+zip)
    Pick newest lead.
    """
    loc = frappe.db.get_value("BTM Location", location_name, ["address_line1", "zip_code"], as_dict=True)
    if not loc or not loc.address_line1 or not loc.zip_code:
        return None

    fp = _fingerprint(loc.address_line1, loc.zip_code)

    lead = frappe.db.sql(
        """
        SELECT l.name
        FROM `tabATM Leads` l
        WHERE l.company = %s
          AND CONCAT(LOWER(TRIM(REPLACE(REPLACE(l.address, '\n', ' '), '\r', ' '))), '|', TRIM(l.zip_code)) IS NOT NULL
        ORDER BY l.creation DESC
        LIMIT 50
        """,
        (operator_company,),
        as_dict=True,
    )

    # strict fingerprint matching in python (safe)
    for r in lead:
        lrow = frappe.db.get_value("ATM Leads", r.name, ["address", "zip_code"], as_dict=True)
        if not lrow:
            continue
        if _fingerprint(lrow.address, lrow.zip_code) == fp:
            return r.name

    return None

def run(limit: int = 0, commit_every: int = 200, overwrite: int = 0, relink_missing: int = 1):
    """
    Fill all milestone dates in Operator Deal.
    - overwrite=0 keeps existing values
    - relink_missing=1 tries to recover missing source_atm_lead by matching operator+address fingerprint
    """
    deals = frappe.get_all(
        "Operator Deal",
        fields=["name", "source_atm_lead", "location", "operator_company", "creation"],
        limit=limit or None
    )

    updated = 0
    skipped = 0
    relinked = 0
    missing_lead = 0

    for i, d in enumerate(deals, start=1):
        deal = frappe.get_doc("Operator Deal", d.name)

        lead_name = deal.source_atm_lead
        if lead_name and not frappe.db.exists("ATM Leads", lead_name):
            lead_name = None

        # relink if missing
        if not lead_name and int(relink_missing) == 1 and deal.location and deal.operator_company:
            found = _find_atm_lead_by_location_and_operator(deal.location, deal.operator_company)
            if found:
                deal.source_atm_lead = found
                lead_name = found
                relinked += 1

        if not lead_name:
            # safe fallback: at least submitted_date
            if not deal.submitted_date:
                deal.submitted_date = deal.creation
                deal.save(ignore_permissions=True)
                updated += 1
            else:
                skipped += 1
            missing_lead += 1
            continue

        before = deal.as_dict()

        # fill from child table history
        apply_milestone_dates_from_lead_history(deal, lead_name, overwrite=bool(int(overwrite)))

        # if still no submitted_date, use lead.creation
        if not deal.submitted_date:
            lc = frappe.db.get_value("ATM Leads", lead_name, "creation")
            if lc:
                deal.submitted_date = lc

        # save only if changed
        after = deal.as_dict()
        if before != after:
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
        "relinked": relinked,
        "missing_lead": missing_lead
    }
