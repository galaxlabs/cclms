import json
import re
from collections import Counter

import frappe
from frappe.utils import get_datetime, now_datetime

from cclms.services.zipintel.intelligence import build_lead_intelligence

DEFAULT_CUTOFF = "2025-08-01"

DEFAULT_STATUS_MAP = {
    "Draft": "Draft",
    "Pending": "Submitted",
    "Called": "Submitted",
    "Call Back": "Submitted",
    "Interested": "Submitted",
    "Not Interested": "Cancelled",
    "Not Qualified": "Rejected",
    "Submitted": "Submitted",
    "Approved": "Approved",
    "Rejected": "Rejected",
    "Needs Reanalysis": "Needs Reanalysis",
    "Agreement Sent": "Agreement Sent",
    "Requested for Agreement Sent": "Agreement Sent",
    "Pending Sign": "Agreement Sent",
    "Signed": "Signed",
    "Resigned": "Signed",
    "Converted": "Converted",
    "Install Scheduled": "Install Scheduled",
    "Installed": "Installed",
    "installed/Removed": "Installed",
    "Signed Rejected": "Rejected",
    "Disputed": "Disputed",
    "Cancelled": "Cancelled",
    "Hide": "Cancelled",
    "Re Approval": "Disputed",
}

MILESTONE_STATE_MAP = {
    "approved_date": {"Approved"},
    "rejected_date": {"Rejected", "Signed Rejected", "Not Qualified"},
    "needs_reanalysis_date": {"Needs Reanalysis"},
    "agreement_sent_date": {"Agreement Sent", "Requested for Agreement Sent", "Pending Sign"},
    "signed_date": {"Signed", "Resigned"},
    "converted_date": {"Converted"},
    "install_scheduled_date": {"Install Scheduled"},
    "installed_date": {"Installed", "installed/Removed", "Removed"},
    "cancelled_date": {"Cancelled", "Hide", "Not Interested"},
    "disputed_date": {"Disputed", "Re Approval"},
}

STATUS_TO_DATE_FIELD = {
    "Submitted": "submitted_date",
    "Approved": "approved_date",
    "Rejected": "rejected_date",
    "Needs Reanalysis": "needs_reanalysis_date",
    "Agreement Sent": "agreement_sent_date",
    "Signed": "signed_date",
    "Converted": "converted_date",
    "Install Scheduled": "install_scheduled_date",
    "Installed": "installed_date",
    "Cancelled": "cancelled_date",
    "Disputed": "disputed_date",
}

SIGNED_LOCK_STATES = ("Signed", "Installed")
REJECTED_LOCK_STATES = ("Rejected",)


def _doctype_exists(doctype_name):
    return bool(frappe.db.exists("DocType", doctype_name))


def _safe_single_value(doctype_name, fieldname, default=None):
    if not _doctype_exists(doctype_name):
        return default
    value = frappe.db.get_single_value(doctype_name, fieldname)
    return default if value in (None, "") else value


def get_cutoff_datetime():
    return get_datetime(_safe_single_value("Operator Deal Settings", "cutoff_date", DEFAULT_CUTOFF))


def get_status_mapping():
    raw = _safe_single_value("Operator Deal Settings", "status_mapping_json")
    if not raw:
        return DEFAULT_STATUS_MAP

    try:
        parsed = json.loads(raw)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Operator Deal Settings invalid status_mapping_json")
        return DEFAULT_STATUS_MAP

    return parsed if isinstance(parsed, dict) else DEFAULT_STATUS_MAP


def normalize_text(value):
    value = re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower())
    return " ".join(value.split())


def build_address_fingerprint(address, zip_code):
    normalized_zip = (zip_code or "").strip()
    normalized_address = normalize_text(address)
    if not normalized_address and not normalized_zip:
        return None
    return f"{normalized_address}|{normalized_zip}"


def get_history_rows(lead_name):
    if not lead_name:
        return []

    return frappe.db.sql(
        """
        SELECT
            to_state,
            change_datetime,
            change_date
        FROM `tabATM Lead State History`
        WHERE parent = %s
        ORDER BY COALESCE(change_datetime, change_date) ASC
        """,
        (lead_name,),
        as_dict=True,
    )


def derive_milestone_dates(lead):
    rows = get_history_rows(lead.name)
    milestone_dates = {}

    post_date = getattr(lead, "post_date", None)
    if post_date:
        milestone_dates["submitted_date"] = get_datetime(post_date)
    elif getattr(lead, "creation", None):
        milestone_dates["submitted_date"] = get_datetime(lead.creation)

    for row in rows:
        state = (row.get("to_state") or "").strip()
        dt = row.get("change_datetime") or row.get("change_date")
        if not state or not dt:
            continue

        dt = get_datetime(dt)
        for fieldname, states in MILESTONE_STATE_MAP.items():
            if state in states and fieldname not in milestone_dates:
                milestone_dates[fieldname] = dt

    current_status = map_lead_status(getattr(lead, "workflow_state", None))
    current_field = STATUS_TO_DATE_FIELD.get(current_status)
    if current_field and current_field not in milestone_dates and getattr(lead, "modified", None):
        milestone_dates[current_field] = get_datetime(lead.modified)

    return milestone_dates


def lead_in_scope(lead, cutoff_dt=None):
    cutoff_dt = cutoff_dt or get_cutoff_datetime()

    creation = get_datetime(lead.creation) if getattr(lead, "creation", None) else None
    modified = get_datetime(lead.modified) if getattr(lead, "modified", None) else None

    if creation and creation >= cutoff_dt:
        return True
    if modified and modified >= cutoff_dt:
        return True

    return bool(
        frappe.db.sql(
            """
            SELECT 1
            FROM `tabATM Lead State History`
            WHERE parent = %s
              AND COALESCE(change_datetime, change_date) >= %s
            LIMIT 1
            """,
            (lead.name, cutoff_dt),
        )
    )


def get_leads_since_cutoff(cutoff_date=None, limit=200, offset=0):
    cutoff_dt = get_datetime(cutoff_date or get_cutoff_datetime())
    return frappe.db.sql(
        """
        SELECT l.name
        FROM `tabATM Leads` l
        LEFT JOIN (
            SELECT parent, MAX(COALESCE(change_datetime, change_date)) AS last_history_change
            FROM `tabATM Lead State History`
            GROUP BY parent
        ) h ON h.parent = l.name
        WHERE l.workflow_state != 'Draft'
          AND (
            l.creation >= %(cutoff)s
            OR l.modified >= %(cutoff)s
            OR h.last_history_change >= %(cutoff)s
          )
        ORDER BY COALESCE(h.last_history_change, l.modified, l.creation) ASC, l.name ASC
        LIMIT %(offset)s, %(limit)s
        """,
        {"cutoff": cutoff_dt, "offset": int(offset), "limit": int(limit)},
        as_dict=True,
    )


def _set_if_present(target, fieldname, value):
    if fieldname not in target.meta.get_valid_columns():
        return
    if value not in (None, ""):
        target.set(fieldname, value)


def resolve_sales_agent(lead):
    agent_name = (getattr(lead, "executive_name", None) or "").strip()
    if not agent_name or not _doctype_exists("Sales Agent"):
        return None

    return frappe.db.get_value("Sales Agent", {"agent_name": agent_name}, "name")


def resolve_assigned_user(lead, sales_agent_name=None):
    sales_agent_name = sales_agent_name or resolve_sales_agent(lead)
    if sales_agent_name and _doctype_exists("Sales Agent"):
        user = frappe.db.get_value("Sales Agent", sales_agent_name, "user")
        if user:
            return user
    return None


def map_lead_status(workflow_state):
    mapping = get_status_mapping()
    return mapping.get((workflow_state or "").strip(), "Draft")


def get_or_create_operator(operator_name):
    existing = frappe.db.get_value("Operator", {"operator_name": operator_name}, "name")
    if existing:
        return frappe.get_doc("Operator", existing)

    operator = frappe.get_doc(
        {
            "doctype": "Operator",
            "operator_name": operator_name,
            "active": 1,
        }
    )
    operator.insert(ignore_permissions=True)
    return operator


def get_or_create_location(lead):
    google_place_id = getattr(lead, "google_place_id", None)
    if google_place_id:
        existing = frappe.db.get_value("BTM Location", {"google_place_id": google_place_id}, "name")
        if existing:
            location = frappe.get_doc("BTM Location", existing)
        else:
            location = frappe.new_doc("BTM Location")
            location.google_place_id = google_place_id
    else:
        existing = frappe.db.get_value(
            "BTM Location",
            {"address_fingerprint": build_address_fingerprint(lead.address, lead.zip_code)},
            "name",
        )
        location = frappe.get_doc("BTM Location", existing) if existing else frappe.new_doc("BTM Location")

    location.location_name = getattr(lead, "business_name", None) or getattr(lead, "owner_name", None) or lead.name
    _set_if_present(location, "business_type", getattr(lead, "business_type", None))
    _set_if_present(location, "address_line1", getattr(lead, "address", None))
    _set_if_present(location, "city", getattr(lead, "city", None))
    _set_if_present(location, "state", getattr(lead, "state", None))
    _set_if_present(location, "zip_code", getattr(lead, "zip_code", None))
    _set_if_present(location, "lat", getattr(lead, "latitude", None))
    _set_if_present(location, "lng", getattr(lead, "longitude", None))
    _set_if_present(location, "owner_contact_name", getattr(lead, "owner_name", None))
    _set_if_present(location, "owner_email", getattr(lead, "email", None))
    _set_if_present(location, "google_place_id", google_place_id)
    _set_if_present(location, "address_fingerprint", build_address_fingerprint(lead.address, lead.zip_code))

    location.flags.ignore_mandatory = False
    location.save(ignore_permissions=True)
    return location


def refresh_location_summary(location_name):
    if not location_name:
        return

    rows = frappe.get_all(
        "Operator Deal",
        filters={"location": location_name},
        fields=["status", "operator_company"],
        order_by="modified desc",
    )

    status_summary = "Open"
    locked_reason = ""
    locked_on = None

    if any(row.status in REJECTED_LOCK_STATES for row in rows):
        status_summary = "Locked Rejected"
        rejected = next(row for row in rows if row.status in REJECTED_LOCK_STATES)
        locked_reason = f"Rejected by {rejected.operator_company}"
        locked_on = now_datetime()
    elif any(row.status in SIGNED_LOCK_STATES for row in rows):
        status_summary = "Locked SignedInstalled"
        signed = next(row for row in rows if row.status in SIGNED_LOCK_STATES)
        locked_reason = f"{signed.status} with {signed.operator_company}"
        locked_on = now_datetime()

    frappe.db.set_value(
        "BTM Location",
        location_name,
        {
            "status_summary": status_summary,
            "locked_reason": locked_reason,
            "locked_on": locked_on,
        },
        update_modified=False,
    )


def sync_atm_lead(lead, mode="live", overwrite=False):
    cutoff_dt = get_cutoff_datetime()
    if not lead_in_scope(lead, cutoff_dt=cutoff_dt):
        return {"status": "skipped", "reason": "before_cutoff", "lead": lead.name}

    operator_name = (getattr(lead, "company", None) or "").strip()
    if not operator_name:
        return {"status": "skipped", "reason": "missing_operator", "lead": lead.name}

    if not getattr(lead, "address", None) or not getattr(lead, "zip_code", None):
        return {"status": "skipped", "reason": "missing_address_zip", "lead": lead.name}

    operator = get_or_create_operator(operator_name)
    location = get_or_create_location(lead)

    deal_name = frappe.db.get_value(
        "Operator Deal",
        {"location": location.name, "operator_company": operator.name},
        "name",
    )
    deal = frappe.get_doc("Operator Deal", deal_name) if deal_name else frappe.new_doc("Operator Deal")

    sales_agent = resolve_sales_agent(lead)
    assigned_user = resolve_assigned_user(lead, sales_agent_name=sales_agent)
    milestone_dates = derive_milestone_dates(lead)
    mapped_status = map_lead_status(getattr(lead, "workflow_state", None))
    validation = build_lead_intelligence(lead, write_zip_centroid=True)

    deal.location = location.name
    deal.operator_company = operator.name
    deal.source_atm_lead = lead.name
    _set_if_present(deal, "sales_agent", sales_agent)
    _set_if_present(deal, "sales_agent_name_text", getattr(lead, "executive_name", None))
    _set_if_present(deal, "assigned_agent", assigned_user)
    _set_if_present(deal, "business_type", getattr(lead, "business_type", None))
    _set_if_present(deal, "tier", getattr(lead, "tier", None))
    deal.status = mapped_status

    for fieldname, value in milestone_dates.items():
        if overwrite or not deal.get(fieldname):
            deal.set(fieldname, value)

    if not deal.get("submitted_date"):
        deal.submitted_date = milestone_dates.get("submitted_date") or get_datetime(lead.creation)

    current_date_field = STATUS_TO_DATE_FIELD.get(deal.status)
    if mode == "live" and current_date_field and not deal.get(current_date_field):
        deal.set(current_date_field, now_datetime())

    if mode != "live":
        deal.flags.in_backfill = True
        deal.flags.skip_strict_duplicate_validation = True

    _set_if_present(deal, "tier_suggestion", validation.get("zone_color"))
    _set_if_present(deal, "competitor_density_score", validation.get("competitor_density_score"))
    _set_if_present(deal, "risk_score", validation.get("risk_score"))
    _set_if_present(deal, "operator_fit_score", validation.get("operator_fit_score"))
    _set_if_present(deal, "recommended_next_action", validation.get("recommended_next_action"))
    _set_if_present(deal, "zip_matched_rule", validation.get("matched_rule"))
    _set_if_present(deal, "last_enriched_on", now_datetime())

    deal.save(ignore_permissions=True)
    refresh_location_summary(location.name)
    return {"status": "ok", "lead": lead.name, "deal": deal.name, "location": location.name}


def sync_atm_lead_live(doc, method=None):
    if int(_safe_single_value("Operator Deal Settings", "live_sync_enabled", 1)) != 1:
        return None

    try:
        return sync_atm_lead(doc, mode="live", overwrite=False)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"ATM Lead live sync failed for {doc.name}")
        return None


def rebuild_from_cutoff(cutoff_date=None, limit=200, offset=0, commit_every=200, stop_on_error=0):
    cutoff_dt = get_datetime(cutoff_date or get_cutoff_datetime())
    lead_rows = get_leads_since_cutoff(cutoff_dt, limit=limit, offset=offset)

    ok = 0
    fail = 0
    skipped = 0
    reasons = Counter()

    for idx, row in enumerate(lead_rows, start=1):
        savepoint = f"od_sync_{offset}_{idx}"
        frappe.db.savepoint(savepoint)

        try:
            lead = frappe.get_doc("ATM Leads", row.name)
            result = sync_atm_lead(lead, mode="backfill", overwrite=False)
            if result.get("status") == "ok":
                ok += 1
            else:
                skipped += 1
                reasons[result.get("reason") or "skipped"] += 1
        except Exception:
            fail += 1
            frappe.db.rollback(save_point=savepoint)
            reasons["error"] += 1
            frappe.log_error(frappe.get_traceback(), f"Operator Deal rebuild failed for {row.name}")
            if int(stop_on_error) == 1:
                raise

        if commit_every and idx % int(commit_every) == 0:
            frappe.db.commit()

    frappe.db.commit()
    return {
        "cutoff_date": str(cutoff_dt.date()),
        "offset": int(offset),
        "processed_in_batch": len(lead_rows),
        "next_offset": int(offset) + len(lead_rows),
        "ok": ok,
        "fail": fail,
        "skipped": skipped,
        "reasons": dict(reasons),
    }


def backfill_dates(limit=0, offset=0, commit_every=200, overwrite=0):
    overwrite = bool(int(overwrite))
    deals = frappe.get_all(
        "Operator Deal",
        fields=["name", "source_atm_lead"],
        order_by="modified asc",
        start=int(offset),
        limit=int(limit) if int(limit or 0) else None,
    )

    updated = 0
    skipped = 0
    missing_lead = 0

    for idx, deal_row in enumerate(deals, start=1):
        lead_name = (deal_row.source_atm_lead or "").strip()
        if not lead_name or not frappe.db.exists("ATM Leads", lead_name):
            skipped += 1
            missing_lead += 1
            continue

        lead = frappe.get_doc("ATM Leads", lead_name)
        milestone_dates = derive_milestone_dates(lead)
        changes = {}

        for fieldname, value in milestone_dates.items():
            if not value:
                continue
            existing_value = frappe.db.get_value("Operator Deal", deal_row.name, fieldname)
            if overwrite or not existing_value:
                if existing_value != value:
                    changes[fieldname] = value

        current_status = frappe.db.get_value("Operator Deal", deal_row.name, "status")
        current_field = STATUS_TO_DATE_FIELD.get(current_status)
        if current_field and current_field not in changes:
            existing_current = frappe.db.get_value("Operator Deal", deal_row.name, current_field)
            fallback_current = milestone_dates.get(current_field)
            if fallback_current and (overwrite or not existing_current):
                changes[current_field] = fallback_current

        if changes:
            frappe.db.set_value("Operator Deal", deal_row.name, changes, update_modified=False)
            updated += 1
        else:
            skipped += 1

        if commit_every and idx % int(commit_every) == 0:
            frappe.db.commit()

    frappe.db.commit()
    return {
        "processed": len(deals),
        "updated": updated,
        "skipped": skipped,
        "missing_lead": missing_lead,
        "overwrite": int(overwrite),
        "next_offset": int(offset) + len(deals),
    }
