# cclms/api/atm_radar.py
from cclms.api.lead import get_leads
from typing import List, Dict, Any, Optional
import frappe

@frappe.whitelist(allow_guest=False)
def get_leads_by_state(...):
    # map your inputs to the new API
    return get_leads(
        company=company,
        executive_name=executive_name,
        status_in=status_in,
        limit=limit,   # if you keep arg name "limit" then pass to limit_page_length
    )
# --- Helpers -----------------------------------------------------------------

def _state_filter(state_or_code: Optional[str]) -> List[List[Any]]:
    """
    Accepts either 'CA' or 'California' and filters against both state_code and state.
    Returns an OR filter list usable in frappe.get_all.
    """
    if not state_or_code:
        return []
    s = state_or_code.strip()
    return [
        ["state_code", "=", s],
        ["state", "=", s],
    ]

def _base_fields() -> List[str]:
    return [
        "name",
        "company",
        "executive_name",
        "workflow_state",
        "address",
        "city",
        "state",
        "state_code",
        "zip_code",
        "country",
        "latitude",
        "longitude",
        "post_date",
        "sign_date",
        "agreement_sent_date",
        "approved_date",
        "converted_date",
    ]

# --- API: Google key ---------------------------------------------------------

@frappe.whitelist(allow_guest=False)
def get_google_maps_key() -> Dict[str, str]:
    """
    Return the Google Maps API key stored in 'Google Maps Settings' (Single Doctype).
    Requires login (avoid exposing keys publicly).
    """
    api_key = frappe.db.get_single_value("Google Maps Settings", "api_key")
    if not api_key:
        frappe.throw("Google Maps API key is not configured in Google Maps Settings.")
    return {"api_key": api_key}

# --- API: Leads by state -----------------------------------------------------

@frappe.whitelist(allow_guest=False)
def get_leads_by_state(
    state: Optional[str] = None,
    company: Optional[str] = None,
    executive_name: Optional[str] = None,
    status_in: Optional[str] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """
    Fetch ATM Leads (non-Draft) for a US state or state_code, optionally filtered by company,
    executive, and workflow_state list. Only returns rows with lat/lng populated.

    Args:
      state: e.g., "CA" or "California". If omitted, returns up to 'limit' rows from all US states.
      company: filter by Operator Companies link
      executive_name: filter by Sales Agent link
      status_in: CSV list of workflow states to include (e.g. "Approved,Signed,Converted")
      limit: max rows (server-side safety)

    Returns:
      { "rows": [...], "meta": {...} }
    """
    f_and = [
        ["doctype", "=", "ATM Leads"],  # harmless, explicit
        ["workflow_state", "!=", "Draft"],
        ["country", "=", "United States"],  # you asked to limit to USA
    ]

    # Optional filters
    if company:
        f_and.append(["company", "=", company])

    if executive_name:
        f_and.append(["executive_name", "=", executive_name])

    # State or state_code: OR between code and long name
    f_or = _state_filter(state)

    # Status filter (CSV -> list)
    status_list = None
    if status_in:
        status_list = [s.strip() for s in status_in.split(",") if s.strip()]
        if status_list:
            f_and.append(["workflow_state", "in", status_list])

    # Query (we want rows that already have coordinates)
    rows = frappe.get_all(
        "ATM Leads",
        filters=f_and,
        or_filters=f_or,
        fields=_base_fields(),
        order_by="modified desc",
        limit_page_length=min(int(limit or 1000), 5000),  # safety cap
    )

    # Only markers with coordinates
    markers = [r for r in rows if r.get("latitude") and r.get("longitude")]

    # Simple counts by status
    by_status = {}
    for r in rows:
        st = r.get("workflow_state") or "Unknown"
        by_status[st] = by_status.get(st, 0) + 1

    # Simple counts by executive (only for those who have any leads returned)
    by_exec = {}
    for r in rows:
        ex = r.get("executive_name") or "—"
        by_exec[ex] = by_exec.get(ex, 0) + 1

    return {
        "rows": markers,
        "meta": {
            "queried": len(rows),
            "with_coordinates": len(markers),
            "by_status": by_status,
            "by_executive": by_exec,
            "state": state,
            "company": company,
            "executive_name": executive_name,
            "status_in": status_list or [],
        },
    }
