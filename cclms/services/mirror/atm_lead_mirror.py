import frappe
from frappe.utils import now_datetime

LEAD_TO_DEAL_STATUS = {
    "Draft": "Draft",
    "Pending": "Submitted",
    "Called": "Under Review",
    "Call Back": "Under Review",
    "Interested": "Under Review",
    "Not Interested": "Cancelled",
    "Not Qualified": "Rejected",
    "Approved": "Approved",
    "Rejected": "Rejected",
    "Needs Reanalysis": "Needs Reanalysis",
    "Agreement Sent": "Agreement Sent",
    "Requested for Agreement Sent": "Agreement Sent",
    "Pending Sign": "Agreement Sent",
    "Signed": "Signed",
    "Resigned": "Signed",
    "Converted": "Converted",
    "Installed": "Installed",
    "installed/Removed": "Installed",
    "Signed Rejected": "Rejected",
    "Disputed": "Disputed",
    "Cancelled": "Cancelled",
    "Hide": "Cancelled",
    "Re Approval": "Disputed",
}

STATUS_DATE_FIELD = {
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

def upsert_from_atm_lead(lead, method=None):
    """
    Mirror ATM Leads -> (Operator, BTM Location, Operator Deal)
    WITHOUT changing ATM Leads DocType.
    """
    operator_name = (lead.get("company") or "").strip()
    if not operator_name:
        return

    operator = _get_or_create_operator(operator_name)
    location = _get_or_create_location_from_lead(lead)
    if not location:
        return

    # global lock rules (as you defined)
    _enforce_global_locks(location.name)

    deal_name = frappe.db.get_value(
        "Operator Deal",
        {"location": location.name, "operator_company": operator.name},
        "name"
    )

    deal = frappe.get_doc("Operator Deal", deal_name) if deal_name else frappe.new_doc("Operator Deal")
    deal.location = location.name
    deal.operator_company = operator.name
    deal.source_atm_lead = lead.name

    # mapping fields from ATM Leads
    deal.assigned_agent = lead.get("lead_owner") or lead.get("executive_name") or lead.get("executive_name_ps")
    deal.business_type = lead.get("business_type")
    deal.status = _map_status(lead.get("workflow_state"))

    # stamp date for this status if empty
    _stamp_status_date(deal)

    deal.save(ignore_permissions=True)

def _map_status(workflow_state: str | None) -> str:
    if not workflow_state:
        return "Draft"
    return LEAD_TO_DEAL_STATUS.get(workflow_state, "Under Review")

def _stamp_status_date(deal):
    fieldname = STATUS_DATE_FIELD.get(deal.status)
    if fieldname and not deal.get(fieldname):
        deal.set(fieldname, now_datetime())

def _enforce_global_locks(location_name: str):
    # If any deal for this location is Rejected => block
    if frappe.db.exists("Operator Deal", {"location": location_name, "status": "Rejected"}):
        frappe.throw("This location was rejected by an operator. New deals are blocked for this location.")

    # If any deal for this location is Signed/Installed => block
    if frappe.db.exists("Operator Deal", {"location": location_name, "status": ["in", ["Signed", "Installed"]]}):
        frappe.throw("This location is already Signed/Installed. New deals are blocked for this location.")

def _get_or_create_operator(operator_name: str):
    name = frappe.db.get_value("Operator", {"operator_name": operator_name}, "name")
    if name:
        return frappe.get_doc("Operator", name)
    d = frappe.new_doc("Operator")
    d.operator_name = operator_name
    d.active = 1
    d.insert(ignore_permissions=True)
    return d

def _fingerprint_address(address: str, zip_code: str) -> str:
    addr = " ".join((address or "").lower().split())
    z = (zip_code or "").strip()
    return f"{addr}|{z}"

def _get_or_create_location_from_lead(lead):
    address = (lead.get("address") or "").strip()
    zip_code = (lead.get("zip_code") or "").strip()

    # If missing required data, skip this lead (do not fail whole backfill)
    if not address or not zip_code:
        frappe.log_error(
            title="Mirror skipped: missing address/zip",
            message=f"ATM Leads {lead.name} missing address or zip_code. address='{address}' zip='{zip_code}'"
        )
        return None

    fingerprint = _fingerprint_address(address, zip_code)

    existing = frappe.db.get_value("BTM Location", {"address_fingerprint": fingerprint}, "name")
    if existing:
        return frappe.get_doc("BTM Location", existing)

    loc = frappe.new_doc("BTM Location")
    loc.address_fingerprint = fingerprint
    loc.location_name = lead.get("business_name") or ""
    loc.owner_contact_name = lead.get("owner_name") or ""
    loc.owner_email = lead.get("email") or ""
    loc.owner_phone = lead.get("business_phone_number") or lead.get("personal_cell_phone") or ""
    loc.address_line1 = address
    loc.city = lead.get("city")
    loc.state = lead.get("state_code")
    loc.zip_code = zip_code
    loc.business_type = lead.get("business_type")
    loc.insert(ignore_permissions=True)
    return loc
