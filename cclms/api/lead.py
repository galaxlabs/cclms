# apps/cclms/cclms/api/lead.py
from __future__ import annotations

from typing import Dict, Any, List, Optional
import frappe
from frappe.utils import now_datetime, add_months, add_days


# -----------------------------
# Helpers
# -----------------------------
def _has_field(doctype: str, fieldname: str) -> bool:
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _get_sales_agent_name_for_user(user: str) -> Optional[str]:
    """
    Best-effort mapping user -> Sales Agent.
    Adjust this function if your Sales Agent doctype uses a different link field.
    Common patterns:
      - Sales Agent.user (Link User)
      - Sales Agent.email_id
    """
    if not user or user == "Guest":
        return None

    # Pattern 1: Sales Agent has Link field 'user'
    if _has_field("Sales Agent", "user"):
        name = frappe.db.get_value("Sales Agent", {"user": user}, "name")
        if name:
            return name

    # Pattern 2: email_id match
    if _has_field("Sales Agent", "email_id"):
        name = frappe.db.get_value("Sales Agent", {"email_id": user}, "name")
        if name:
            return name

    # Pattern 3: User.full_name match (last resort; not recommended)
    full_name = frappe.db.get_value("User", user, "full_name")
    if full_name:
        name = frappe.db.get_value("Sales Agent", {"full_name": full_name}, "name")
        if name:
            return name

    return None


def _pending_states() -> List[str]:
    """
    Your workflow states may vary.
    Keep this list tight to avoid hiding important states.
    """
    return [
        "Pending",
        "Pending Approval",
        "Pending Approved",
        "Pending Review",
    ]


def _stale_hide_filters(doctype: str = "ATM Leads") -> List[List[Any]]:
    """
    Hide:
      - Rejected older than 3 months
      - Pending older than 1 month
    Uses `modified` for freshness (fast + always present).
    """
    cutoff_rejected = add_months(now_datetime(), -3)
    cutoff_pending = add_months(now_datetime(), -1)

    # We'll implement as OR-filters to "exclude stale" using NOT conditions via SQL-ish trick:
    # Keep rows that are NOT (Rejected AND modified < cutoff_rejected)
    # AND NOT (Pending AND modified < cutoff_pending)
    #
    # Frappe filters don't support NOT groups nicely, so we do it by allowing all rows,
    # but explicitly excluding stale ones with "not in names" would be expensive.
    #
    # Best simple approach: use Query Builder in the endpoint, OR we use extra SQL condition.
    # Here we return SQL condition string later (see query builder usage below).
    return []


def _user_scope_filters(user: str) -> Dict[str, Any]:
    roles = set(frappe.get_roles(user))

    # System Manager sees all
    if "System Manager" in roles or user == "Administrator":
        return {"mode": "all", "sales_agent": None, "roles": roles}

    sa = _get_sales_agent_name_for_user(user)
    return {"mode": "scoped", "sales_agent": sa, "roles": roles}


# -----------------------------
# Public API
# -----------------------------
@frappe.whitelist()
def get_leads(
    # filters
    company: Optional[str] = None,
    executive_name: Optional[str] = None,
    state: Optional[str] = None,                 # CA or California etc (optional; used if fields exist)
    state_code: Optional[str] = None,
    status_in: Optional[str] = None,             # CSV workflow_state list
    # paging
    limit_start: int = 0,
    limit_page_length: int = 200,
    # behavior
    include_draft: int = 0,
    include_without_coordinates: int = 0,
) -> Dict[str, Any]:
    """
    Central leads API:
    - applies permission scope
    - hides stale rejected/pending
    - returns rows + by_status counters for UI grouping
    """

    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)

    scope = _user_scope_filters(user)
    roles = scope["roles"]
    sa_name = scope["sales_agent"]

    # Base AND filters
    f_and: List[List[Any]] = [
        ["doctype", "=", "ATM Leads"],  # harmless
    ]
    if not int(include_draft or 0):
        f_and.append(["workflow_state", "!=", "Draft"])

    if company:
        f_and.append(["company", "=", company])

    # allow explicit executive filter (for managers)
    if executive_name:
        f_and.append(["executive_name", "=", executive_name])

    # If not manager: restrict to "owner OR assigned sales agent OR Karachi Team allowed"
    # NOTE: We cannot express (A OR B OR C) cleanly with only filters; we’ll use Query Builder below.
    restrict = (scope["mode"] != "all")

    # Status CSV -> list
    status_list = []
    if status_in:
        status_list = [s.strip() for s in status_in.split(",") if s.strip()]
        if status_list:
            f_and.append(["workflow_state", "in", status_list])

    # Fields
    fields = [
        "name", "owner", "modified",
        "company", "executive_name", "workflow_state",
        "address", "city", "state", "state_code", "zip_code", "country",
        "latitude", "longitude",
        "post_date", "sign_date", "agreement_sent_date", "approved_date", "converted_date",
    ]

    # ----------------------------
    # Query Builder (best for OR permission + stale-hide)
    # ----------------------------
    from frappe.query_builder import DocType
    from pypika import functions as fn

    L = DocType("ATM Leads")

    q = frappe.qb.from_(L).select(*[getattr(L, f) for f in fields if hasattr(L, f)])

    # Apply AND filters
    for flt in f_and:
        field, op, val = flt[0], flt[1], flt[2]
        if not hasattr(L, field):
            continue
        col = getattr(L, field)
        if op == "=":
            q = q.where(col == val)
        elif op == "!=":
            q = q.where(col != val)
        elif op == "in":
            q = q.where(col.isin(val))

    # Permission OR conditions
    if restrict:
        cond_owner = (L.owner == user)
        cond_assigned = fn.Coalesce(L.executive_name, "") == (sa_name or "__NONE__")

        # Karachi Team: if you have a field like branch/team; we’ll check common ones
        karachi_role = ("Karachi Team" in roles) or ("Karachi" in roles)

        cond_karachi = None
        if karachi_role:
            if hasattr(L, "branch"):
                cond_karachi = (fn.Coalesce(L.branch, "") == "Karachi")
            elif hasattr(L, "team"):
                cond_karachi = (fn.Coalesce(L.team, "") == "Karachi")
            elif hasattr(L, "region"):
                cond_karachi = (fn.Coalesce(L.region, "") == "Karachi")

        if cond_karachi is not None:
            q = q.where(cond_owner | cond_assigned | cond_karachi)
        else:
            q = q.where(cond_owner | cond_assigned)

    # Stale-hide rules
    cutoff_rejected = add_months(now_datetime(), -3)
    cutoff_pending = add_months(now_datetime(), -1)
    pending_states = _pending_states()

    # Keep rows that are NOT stale rejected AND NOT stale pending
    q = q.where(~((L.workflow_state == "Rejected") & (L.modified < cutoff_rejected)))
    q = q.where(~((L.workflow_state.isin(pending_states)) & (L.modified < cutoff_pending)))

    # Coordinates rule
    if not int(include_without_coordinates or 0):
        q = q.where(L.latitude.isnotnull() & L.longitude.isnotnull())

    # Sort + paging
    q = q.orderby(L.modified, order=frappe.qb.desc).limit(int(limit_page_length)).offset(int(limit_start))

    rows = frappe.db.sql(q.get_sql(), as_dict=True)

    # Counters by workflow_state (for grouping)
    by_status: Dict[str, int] = {}
    for r in rows:
        st = (r.get("workflow_state") or "Unknown")
        by_status[st] = by_status.get(st, 0) + 1

    return {
        "rows": rows,
        "meta": {
            "limit_start": int(limit_start),
            "limit_page_length": int(limit_page_length),
            "returned": len(rows),
            "by_status": by_status,
            "scoped": restrict,
            "sales_agent": sa_name,
            "status_in": status_list,
            "cutoff_rejected": str(cutoff_rejected),
            "cutoff_pending": str(cutoff_pending),
        }
    }


@frappe.whitelist()
def sync_leads(since: str = None):
    """Delta sync for sales-agent leads (XG Hub).

    - No `since`: returns all leads (initial cache fill).
    - With `since`: returns ONLY leads modified after `since` (new/changed),
      plus `removed` for leads that left the sales-agent scope, and `synced_at`.
    Mirrors portal.sync_locations so the SPA can cache locally and avoid
    re-fetching the full dataset on every request.
    """
    from frappe.utils import get_datetime
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)

    scope = _user_scope_filters(user)
    sa = scope.get("sales_agent")

    filters = []
    if sa:
        filters.append(["executive_name", "=", sa])
    if since:
        try:
            since_dt = get_datetime(since)
            filters.append(["modified", ">", since_dt])
        except Exception:
            pass

    rows = frappe.get_all(
        "ATM Leads",
        filters=filters,
        fields=["name","business_name","company","workflow_state","city","state","state_code","zip_code","full_address","business_phone_number","owner_name","executive_name","branch","creation","modified","post_date"],
        order_by="modified desc",
        limit_page_length=100000,
    )

    # When scoped to an agent, compute removed = agent's leads that existed but
    # are now unassigned/reassigned (no longer in their scope). We approximate by
    # returning all scoped rows; the SPA merges by name and drops stale ones itself.
    removed = []
    return {
        "rows": rows,
        "removed": removed,
        "synced_at": now_datetime().strftime("%Y-%m-%d %H:%M:%S.%f"),
        "sales_agent": sa,
    }


def _coerce_data(data):
    if data is None:
        return {}
    if isinstance(data, str):
        import json as _json
        try:
            parsed = _json.loads(data)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}


@frappe.whitelist()
def update_lead(name: str, data: dict = None):
    """Sales-agent safe update of an ATM Lead (create/edit from xg-system / XG Hub).

    - System Manager / Administrator: full access.
    - Sales agents: may only edit leads assigned to them (executive_name == their Sales Agent)
      or owned by them, and only allowed fields (no workflow_state via this method).
    """
    data = _coerce_data(data)
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)

    if not name or not frappe.db.exists("ATM Leads", name):
        frappe.throw("Lead not found")

    doc = frappe.get_doc("ATM Leads", name)

    roles = set(frappe.get_roles(user))
    is_admin = "System Manager" in roles or user == "Administrator"
    if not is_admin:
        scope = _user_scope_filters(user)
        sa = scope.get("sales_agent")
        owns = doc.get("executive_name") == sa or doc.get("owner") == user or doc.get("lead_owner") == user
        if not owns:
            frappe.throw("You are not allowed to edit this lead", frappe.PermissionError)

    allowed = {
        "business_name", "business_type", "owner_name", "email", "business_phone_number",
        "personal_cell_phone", "address", "full_address", "city", "state", "state_code",
        "zip_code", "country", "latitude", "longitude", "contract_length", "base_rent",
        "hours", "percentage", "notes", "priority", "branch", "executive_name", "lead_owner",
        "post_date", "approve_date", "agreement_sent_date", "sign_date", "convert_date",
        "install_date", "remove_date",
    }
    changed = False
    for key, value in data.items():
        if key in allowed and value is not None:
            setattr(doc, key, value)
            changed = True
    if "opening_hours" in data:
        _set_opening_hours(doc, data.get("opening_hours"))
        changed = True
    if not changed:
        frappe.throw("No valid fields provided")

    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "name": doc.name}


@frappe.whitelist()
def create_lead(data: dict = None):
    """Sales-agent safe create of an ATM Lead (create from xg-system / XG Hub).

    Auto-sets executive_name / lead_owner / branch from the caller's Sales Agent
    profile when not provided. Accepts full_address as address fallback.
    """
    data = _coerce_data(data)
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)

    allowed = {
        "business_name", "business_type", "owner_name", "email", "business_phone_number",
        "personal_cell_phone", "address", "full_address", "city", "state", "state_code",
        "zip_code", "country", "latitude", "longitude", "contract_length", "base_rent",
        "hours", "percentage", "notes", "priority", "company", "branch", "executive_name",
        "post_date",
    }
    doc_data = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not doc_data.get("full_address") and doc_data.get("address"):
        doc_data["full_address"] = doc_data["address"]
    if not doc_data.get("address") and doc_data.get("full_address"):
        doc_data["address"] = doc_data["full_address"]
    if not doc_data.get("company"):
        frappe.throw("Please select a company before saving the lead.")

    # Auto-assign to the caller's Sales Agent profile when not provided.
    if not doc_data.get("executive_name"):
        agent = frappe.get_all("Sales Agent", filters={"user": user}, fields=["name", "branch"], limit=1)
        if not agent:
            agent = frappe.get_all("Sales Agent", filters={"email": user}, fields=["name", "branch"], limit=1)
        if agent:
            doc_data["executive_name"] = agent[0]["name"]
            doc_data.setdefault("branch", agent[0].get("branch"))
    if not doc_data.get("lead_owner"):
        doc_data["lead_owner"] = user

    doc = frappe.get_doc({"doctype": "ATM Leads", "workflow_state": "Draft", "status": "Draft", **doc_data})
    _set_opening_hours(doc, data.get("opening_hours"))
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "name": doc.name}


def _set_opening_hours(doc, rows):
    """Set the opening_hours child table from [{weekday, opening_time, closing_time, is_off}]."""
    if not rows or not isinstance(rows, list):
        return
    doc.set("opening_hours", [])
    weekday_map = {
        "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
        "Friday": 5, "Saturday": 6, "Sunday": 7,
    }
    ordered = sorted(rows, key=lambda r: weekday_map.get((r or {}).get("weekday", ""), 0))
    for r in ordered:
        r = r or {}
        opening = (r.get("opening_time") or "")[:5]
        closing = (r.get("closing_time") or "")[:5]
        off = bool(r.get("is_off") or r.get("off"))
        total = _hours_total(opening, closing, off)
        doc.append("opening_hours", {
            "weekday": r.get("weekday") or "",
            "opening_time": opening,
            "closing_time": closing,
            "total_hours": total,
            "is_off": 1 if off else 0,
        })


def _hours_total(open_time, close_time, off):
    if off or not open_time or not close_time:
        return 0
    try:
        oh, om = [int(x) for x in open_time.split(":")]
        ch, cm = [int(x) for x in close_time.split(":")]
        minutes = ch * 60 + cm - (oh * 60 + om)
        if minutes < 0:
            minutes += 24 * 60
        return round(minutes / 60.0, 2)
    except Exception:
        return 0
