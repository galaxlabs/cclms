# apps/cclms/cclms/services/mirror/atm_lead_mirror.py
# Dynamic + safe mirror: ATM Leads -> Operator, BTM Location, Operator Deal
# - No hardcoding on Sales Agent fieldnames (auto-detect)
# - No hardcoding on State History child row fieldnames (auto-detect)
# - Status mapping is configurable via hook/cached default
# - Fills milestone dates from ATM Leads.state_history if available
# - Handles link / text agent resolution robustly

import frappe
from frappe.utils import now_datetime, get_datetime


# ----------------------------
# Config (can be overridden via hooks.py)
# ----------------------------

DEFAULT_LEAD_TO_DEAL_STATUS = {
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

DEFAULT_STATUS_DATE_FIELD = {
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

# Milestone inference from ATM Lead State History transitions
DEFAULT_MILESTONE_STATES = {
    "submitted_date": {"Submitted", "Pending"},
    "approved_date": {"Approved"},
    "rejected_date": {"Rejected", "Signed Rejected", "Not Qualified"},
    "needs_reanalysis_date": {"Needs Reanalysis"},
    "agreement_sent_date": {"Agreement Sent", "Requested for Agreement Sent", "Pending Sign"},
    "signed_date": {"Signed", "Resigned"},
    "converted_date": {"Converted"},
    "installed_date": {"Installed", "installed/Removed", "Removed"},
    "cancelled_date": {"Cancelled", "Hide", "Not Interested"},
    "disputed_date": {"Disputed", "Re Approval"},
}
# same as your mapping (keep it)
MILESTONE_STATES = {
    "submitted_date": {"Submitted", "Pending"},
    "approved_date": {"Approved"},
    "rejected_date": {"Rejected", "Signed Rejected", "Not Qualified"},
    "needs_reanalysis_date": {"Needs Reanalysis"},
    "agreement_sent_date": {"Agreement Sent", "Requested for Agreement Sent", "Pending Sign"},
    "signed_date": {"Signed", "Resigned"},
    "converted_date": {"Converted"},
    "installed_date": {"Installed", "installed/Removed", "Removed"},
    "cancelled_date": {"Cancelled", "Hide", "Not Interested"},
    "disputed_date": {"Disputed", "Re Approval"},
}

def _history_rows_from_db(lead_name: str):
    """Fetch ATM Lead State History rows directly (source of truth)."""
    if not lead_name:
        return []
    return frappe.db.sql(
        """
        SELECT
            from_state, to_state,
            change_datetime, change_date
        FROM `tabATM Lead State History`
        WHERE parent = %s
        ORDER BY COALESCE(change_datetime, change_date) ASC
        """,
        (lead_name,),
        as_dict=True,
    )

def _first_dt_from_history_db(lead_name: str, states: set[str]):
    """Return earliest datetime where to_state is in states."""
    rows = _history_rows_from_db(lead_name)
    best = None
    for r in rows:
        st = (r.get("to_state") or "").strip()
        if st not in states:
            continue
        dt = r.get("change_datetime") or r.get("change_date")
        if not dt:
            continue
        dt = get_datetime(dt)
        if best is None or dt < best:
            best = dt
    return best

def apply_milestone_dates_from_lead_history(deal, lead_name: str, overwrite: bool = False):
    """
    Fill Operator Deal milestone dates from child table history.
    """
    for f, states in MILESTONE_STATES.items():
        if not overwrite and deal.get(f):
            continue
        dt = _first_dt_from_history_db(lead_name, states)
        if dt:
            deal.set(f, dt)


def _get_conf(key: str, default):
    """Allow overriding mapping from hooks.py via frappe.get_hooks."""
    try:
        hooks = frappe.get_hooks(key) or []
        if hooks:
            # hooks may return list of dict path strings; accept dict directly too
            val = hooks[0]
            if isinstance(val, dict):
                return val
    except Exception:
        pass
    return default


LEAD_TO_DEAL_STATUS = _get_conf("cclms_lead_to_deal_status", DEFAULT_LEAD_TO_DEAL_STATUS)
STATUS_DATE_FIELD = _get_conf("cclms_status_date_field", DEFAULT_STATUS_DATE_FIELD)
MILESTONE_STATES = _get_conf("cclms_milestone_states", DEFAULT_MILESTONE_STATES)


# ----------------------------
# Entry
# ----------------------------
def upsert_from_atm_lead(lead, method=None):
    mode = "backfill" if method == "backfill" else "live"

    operator_name = (lead.get("company") or "").strip()
    if not operator_name:
        return None

    operator = _get_or_create_operator(operator_name)
    location = _get_or_create_location_from_lead(lead)
    if not location:
        return None

    _enforce_global_locks(location.name, mode=mode)

    deal_name = frappe.db.get_value(
        "Operator Deal",
        {"location": location.name, "operator_company": operator.name},
        "name"
    )

    deal = frappe.get_doc("Operator Deal", deal_name) if deal_name else frappe.new_doc("Operator Deal")
    deal.location = location.name
    deal.operator_company = operator.name
    deal.source_atm_lead = lead.name

    # agent fields
    deal.sales_agent = _resolve_sales_agent_from_lead(lead)
    deal.sales_agent_name_text = _best_agent_text(lead)
    deal.assigned_agent = _resolve_user_from_lead(lead)

    # other mapping
    deal.business_type = lead.get("business_type")
    deal.status = _map_status(lead.get("workflow_state"))

    # ✅ IMPORTANT: fill milestone dates from DB child table (not lead.state_history)
    apply_milestone_dates_from_lead_history(deal, lead.name, overwrite=False)

    # fallback in live mode (only for current status)
    if mode == "live":
        _stamp_status_date_if_missing(deal)
    
    if mode == "backfill":
        deal.flags.in_backfill = True

    deal.save(ignore_permissions=True)
    return deal.name

# def upsert_from_atm_lead(lead, method=None):
#     """
#     Mirror ATM Leads -> (Operator, BTM Location, Operator Deal)
#     WITHOUT changing ATM Leads DocType.

#     method:
#       - "backfill" -> no strict lock blocking, no now() stamping fallback unless needed
#       - default   -> live mode
#     """
#     mode = "backfill" if method == "backfill" else "live"

#     operator_name = (lead.get("company") or "").strip()
#     if not operator_name:
#         return None
#     # instead of reading lead.state_history
#     apply_milestone_dates_from_lead_history(deal, lead.name, overwrite=False)

#     # fallback stamping (live only) if current status date missing
#     if mode == "live":
#         _stamp_status_date_if_missing(deal)

#     operator = _get_or_create_operator(operator_name)
#     location = _get_or_create_location_from_lead(lead)
#     if not location:
#         return None

#     # strict lock rules only in live mode
#     _enforce_global_locks(location.name, mode=mode)

#     deal_name = frappe.db.get_value(
#         "Operator Deal",
#         {"location": location.name, "operator_company": operator.name},
#         "name"
#     )

#     deal = frappe.get_doc("Operator Deal", deal_name) if deal_name else frappe.new_doc("Operator Deal")
#     deal.location = location.name
#     deal.operator_company = operator.name
#     deal.source_atm_lead = lead.name

#     # agent resolution (official Sales Agent + fallback text)
#     deal.sales_agent = _resolve_sales_agent_from_lead(lead)
#     deal.sales_agent_name_text = _best_agent_text(lead)

#     # keep user assignment too (optional) - resolve to User if possible
#     deal.assigned_agent = _resolve_user_from_lead(lead)

#     deal.business_type = lead.get("business_type")
#     deal.tier = lead.get("tier") if _has_field("Operator Deal", "tier") else deal.get("tier")

#     # map status from workflow_state
#     deal.status = _map_status(lead.get("workflow_state"))

#     # fill milestone dates from state_history (dynamic field detection)
#     _apply_milestone_dates_from_state_history(deal, lead, overwrite=False)

#     # fallback stamping in live mode if no history data for that milestone
#     if mode == "live":
#         _stamp_status_date_if_missing(deal)

#     deal.save(ignore_permissions=True)
#     return deal.name


# ----------------------------
# Status mapping
# ----------------------------

def _map_status(workflow_state: str | None) -> str:
    if not workflow_state:
        return "Draft"
    return LEAD_TO_DEAL_STATUS.get(workflow_state.strip(), "Under Review")


def _stamp_status_date_if_missing(deal):
    fieldname = STATUS_DATE_FIELD.get(deal.status)
    if fieldname and not deal.get(fieldname):
        deal.set(fieldname, now_datetime())


# ----------------------------
# Locks
# ----------------------------

def _enforce_global_locks(location_name: str, mode: str = "live"):
    if mode == "backfill":
        return

    if frappe.db.exists("Operator Deal", {"location": location_name, "status": "Rejected"}):
        frappe.throw("This location was rejected by an operator. New deals are blocked for this location.")

    if frappe.db.exists("Operator Deal", {"location": location_name, "status": ["in", ["Signed", "Installed"]]}):
        frappe.throw("This location is already Signed/Installed. New deals are blocked for this location.")


# ----------------------------
# Milestone dates from child table (dynamic)
# ----------------------------

def _apply_milestone_dates_from_state_history(deal, lead, overwrite: bool = False):
    """
    Uses lead.state_history table to fill Operator Deal milestone date fields.
    Dynamic: auto-detects state_history table fieldnames.
    """
    history = getattr(lead, "state_history", None)
    if not history:
        return

    # detect row fieldnames dynamically
    # possible names: to_state / workflow_state, change_datetime / change_date / creation, etc.
    for deal_date_field, states in MILESTONE_STATES.items():
        if not overwrite and deal.get(deal_date_field):
            continue

        dt = _first_dt_from_history_rows(history, states)
        if dt:
            deal.set(deal_date_field, dt)


def _first_dt_from_history_rows(rows, states: set[str]):
    best = None
    for r in rows:
        st = (_row_get(r, ["to_state", "workflow_state", "state", "to"]) or "").strip()
        if not st or st not in states:
            continue

        dt = _row_get(r, ["change_datetime", "change_dt", "modified", "creation"])
        if not dt:
            dt = _row_get(r, ["change_date", "date"])
        if not dt:
            continue

        dt = get_datetime(dt)
        if best is None or dt < best:
            best = dt
    return best


def _row_get(row, keys):
    for k in keys:
        try:
            val = getattr(row, k, None)
        except Exception:
            val = None
        if val:
            return val
        try:
            val = row.get(k)
        except Exception:
            val = None
        if val:
            return val
    return None


# ----------------------------
# Agent resolution (dynamic Sales Agent)
# ----------------------------

def _best_agent_text(lead):
    for key in ("executive_name", "executive_name_ps", "lead_owner"):
        v = (lead.get(key) or "").strip()
        if v:
            return v
    return "Unknown"


def _resolve_sales_agent_from_lead(lead):
    """
    Returns Sales Agent.name if possible, else None.
    Dynamic: tries multiple matching strategies without hardcoded fieldnames.
    """
    # 1) direct link value (executive_name / executive_name_ps might already be Sales Agent.name)
    for key in ("executive_name", "executive_name_ps"):
        val = (lead.get(key) or "").strip()
        if val and frappe.db.exists("Sales Agent", val):
            return val

    # 2) match by common Sales Agent "full name" fields
    # detect an appropriate text field in Sales Agent DocType
    name_field = _detect_sales_agent_name_field()

    for key in ("executive_name", "executive_name_ps", "lead_owner"):
        val = (lead.get(key) or "").strip()
        if not val:
            continue

        if name_field:
            sa = frappe.db.get_value("Sales Agent", {name_field: val}, "name")
            if sa:
                return sa

        # fallback: partial match by name in title field
        sa = frappe.db.sql("""
            SELECT name
            FROM `tabSales Agent`
            WHERE name=%s
               OR COALESCE({nf}, '')=%s
            LIMIT 1
        """.format(nf=name_field or "name"), (val, val))
        if sa:
            return sa[0][0]

    return None


def _detect_sales_agent_name_field():
    """
    Try to find a "human name" field in Sales Agent DocType.
    Common: agent_name, sales_agent_name, employee_name, full_name
    """
    meta = frappe.get_meta("Sales Agent")
    candidates = ["agent_name", "sales_agent_name", "employee_name", "full_name", "name1"]
    fieldnames = {f.fieldname for f in meta.fields}
    for c in candidates:
        if c in fieldnames:
            return c
    return None


def _resolve_user_from_lead(lead):
    """
    Try to resolve to User.name (email) when possible.
    """
    # direct user id/email
    lo = (lead.get("lead_owner") or "").strip()
    if lo and frappe.db.exists("User", lo):
        return lo

    # maybe executive_name stores full name of user
    for key in ("executive_name", "executive_name_ps"):
        nm = (lead.get(key) or "").strip()
        if not nm:
            continue
        user = frappe.db.get_value("User", {"full_name": nm}, "name")
        if user:
            return user
    return None


# ----------------------------
# Operator & Location
# ----------------------------

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

    if not address or not zip_code:
        frappe.log_error(
            title="Mirror skipped: missing address/zip",
            message=f"ATM Leads {lead.name} missing address or zip_code. address='{address}' zip='{zip_code}'",
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


def _has_field(doctype: str, fieldname: str) -> bool:
    try:
        meta = frappe.get_meta(doctype)
        return any(f.fieldname == fieldname for f in meta.fields)
    except Exception:
        return False
