import json
import re
from urllib.parse import urlencode

import frappe
from frappe.utils import get_url, now_datetime

from cclms.api.atm_lead_helper import lookup_existing_lead
from cclms.api.competitor_kiosk_helper import _existing_competitor, _normalize_zip, upsert_competitor_kiosk_from_radar


def _payload(payload=None, **kwargs):
    if isinstance(payload, dict):
        data = dict(payload)
    elif payload:
        data = json.loads(payload)
    else:
        data = {}
    data.update({key: value for key, value in kwargs.items() if value is not None})
    return data


def _clip(value, length=140):
    if value in (None, ""):
        return value
    return str(value)[:length]


def _request_context(payload=None, **kwargs):
    data = _payload(payload, **kwargs)
    place = data.get("place") or {}
    coordinates = place.get("coordinates") or {}
    merged = {
        "device_id": data.get("device_id"),
        "employee": data.get("employee"),
        "source_system": data.get("source_system"),
        "browser_context": data.get("browser_context") or {},
        "page_context": data.get("page_context") or {},
    }
    merged.update(place)
    if coordinates.get("lat") is not None and merged.get("latitude") in (None, ""):
        merged["latitude"] = coordinates.get("lat")
    if coordinates.get("lng") is not None and merged.get("longitude") in (None, ""):
        merged["longitude"] = coordinates.get("lng")
    return merged


def _meta_fields(doctype, candidates):
    meta = frappe.get_meta(doctype)
    available = {field.fieldname for field in meta.fields}
    return [field for field in candidates if field in available]


def _crm_base_url():
    return (get_url() or "").rstrip("/")


def _lead_route(name):
    if not name:
        return ""
    return f"{_crm_base_url()}/app/atm-leads/{name}"


def _new_lead_route(query_values=None):
    new_name = f"new-atm-leads-{frappe.generate_hash(length=10).lower()}"
    route = f"{_crm_base_url()}/app/atm-leads/{new_name}"
    if query_values:
        return f"{route}?{urlencode(query_values)}"
    return route


def _zip_row(zip_code=None, state=None):
    filters = {}
    normalized_zip = _normalize_zip(zip_code)
    if normalized_zip:
        filters["zip_code"] = normalized_zip
    if state:
        filters["state_code"] = str(state).strip().upper()
    fields = _meta_fields(
        "Zip Code Analytics",
        [
            "name",
            "zip_code",
            "city",
            "state_code",
            "zone_color",
            "zip_score",
            "location_flag",
            "competitor_count",
            "competitor_kiosks",
            "company_kiosks",
        ],
    )
    rows = frappe.get_all("Zip Code Analytics", filters=filters, fields=fields, limit_page_length=3)
    return rows[0] if rows else {}


def _lead_matches(data):
    result = lookup_existing_lead(
        address=data.get("address"),
        zip_code=data.get("zip_code"),
        business_name=data.get("place_name") or data.get("business_name") or data.get("name"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
    )
    return result or {}


def _competitor_match(data):
    return _existing_competitor(
        place_id=data.get("place_id") or data.get("external_id"),
        display_name=data.get("name") or data.get("display_name") or data.get("place_name") or data.get("business_name"),
        address=data.get("address"),
        zip_code=data.get("zip_code"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
    )


def _infer_address_parts(address):
    clean = (address or "").strip()
    city = ""
    state = ""
    zip_code = ""
    parts = [part.strip() for part in clean.split(",") if part.strip()]
    if len(parts) >= 2:
        city = parts[-2]
    if parts:
        tokens = parts[-1].split()
        if tokens:
            maybe_state = tokens[0].strip().upper()
            if len(maybe_state) == 2 and maybe_state.isalpha():
                state = maybe_state
    matches = re.findall(r"\b(\d{5})(?:-\d{4})?\b", clean)
    if matches:
        zip_code = matches[-1]
    return city, state, zip_code


def _classify_context(data):
    name = (data.get("name") or data.get("place_name") or data.get("business_name") or "").strip()
    address = (data.get("address") or "").strip()
    category = (data.get("category") or data.get("business_type") or "").strip()
    zip_code = _normalize_zip(data.get("zip_code"))
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not name:
        return "unknown"
    if name.strip().lower() == "google maps":
        return "unknown"
    if category:
        return "business_place"
    if address and zip_code and any(ch.isdigit() for ch in address):
        return "address_place"
    if zip_code and not address and latitude not in (None, "") and longitude not in (None, ""):
        return "zip_area"
    if not address and latitude not in (None, "") and longitude not in (None, ""):
        return "region"
    if not address:
        return "city"
    return "unknown"


def _prefill_values(data):
    raw_zip_code = _normalize_zip(data.get("zip_code"))
    address = (data.get("address") or "").strip()
    city = (data.get("city") or "").strip()
    state = (data.get("state") or data.get("state_code") or "").strip()
    inferred_city, inferred_state, inferred_zip = _infer_address_parts(address)
    city = city or inferred_city
    state = state or inferred_state
    zip_code = raw_zip_code or inferred_zip
    if inferred_zip and raw_zip_code and raw_zip_code != inferred_zip:
        # Google Maps parsers sometimes mistake the street number for the ZIP.
        zip_code = inferred_zip
    return {
        "business_name": data.get("place_name") or data.get("business_name") or data.get("name"),
        "address": address,
        "full_address": address,
        "city": city,
        "state": state,
        "state_code": state,
        "zip_code": zip_code,
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "phone": data.get("phone"),
        "website": data.get("website"),
        "business_type": data.get("category") or data.get("business_type"),
        "source": data.get("source_type") or "Google Maps",
    }


def _zip_summary(zip_row):
    competitor_count = zip_row.get("competitor_count")
    if competitor_count in (None, ""):
        competitor_count = zip_row.get("competitor_kiosks") or 0
    zone_color = zip_row.get("zone_color") or ""
    status = "Proceed"
    if zone_color == "Red":
        status = "Avoid"
    elif zone_color in ("Yellow", "Light Green"):
        status = "Review"
    return {
        "zone_color": zone_color,
        "zip_score": zip_row.get("zip_score") or 0,
        "status": status,
        "competitor_count": competitor_count or 0,
    }


def _validation_message(zip_row, lead_match, competitor_match, context_type=None):
    best = lead_match.get("best_match") or {}
    duplicate_found = bool(best)
    zip_summary = _zip_summary(zip_row)
    recommendation = "Create Prefilled ATM Lead"
    duplicate_reason = ""
    if duplicate_found:
        recommendation = "Open Existing Lead"
        duplicate_reason = f"Location already exists in ATM Leads at workflow state {best.get('workflow_state') or 'Unknown'}"
    elif zip_summary["status"] == "Avoid":
        recommendation = "Avoid"
        duplicate_reason = "ZIP is marked Red in Zip Code Analytics"
    elif zip_summary["status"] == "Review":
        recommendation = "Manual Review"
    if not zip_summary["zone_color"] and not duplicate_found:
        zip_summary["status"] = "Review"
        recommendation = "Manual Review"
    if context_type and context_type not in ("business_place", "address_place") and not duplicate_found:
        recommendation = "Manual Review"

    return {
        "exists_in_atm_leads": duplicate_found,
        "existing_lead_name": best.get("name") or "",
        "workflow_state": best.get("workflow_state") or "",
        "exists_in_competitors": bool(competitor_match),
        "zip_score": zip_summary["zip_score"],
        "zone_color": zip_summary["zone_color"],
        "recommendation": recommendation,
        "duplicate_reason": duplicate_reason,
        "competitor_count": zip_summary["competitor_count"],
        "open_existing_lead_url": _lead_route(best.get("name")),
        "allowed": not duplicate_found and zip_summary["status"] != "Avoid",
        "status": zip_summary["status"],
    }


@frappe.whitelist()
def prefill_atm_lead_context(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    prefill = _prefill_values(data)
    context_type = _classify_context(data)
    zip_row = _zip_row(zip_code=prefill.get("zip_code"), state=prefill.get("state"))
    lead_match = _lead_matches(data)
    competitor_match = _competitor_match(data)
    validation = _validation_message(zip_row, lead_match, competitor_match, context_type=context_type)

    warnings = []
    can_create_lead = context_type in ("business_place", "address_place")
    if context_type not in ("business_place", "address_place"):
        warnings.append("This is an area-level or weak map result, not a specific business location.")
    if validation["exists_in_atm_leads"]:
        warnings.append(f"This location already exists at workflow state: {validation['workflow_state'] or 'Unknown'}")

    query_values = {key: value for key, value in prefill.items() if value not in (None, "")}
    open_url = _new_lead_route(query_values)

    message = {
        "context_type": context_type,
        "can_create_lead": can_create_lead and not validation["exists_in_atm_leads"],
        "requires_manual_review": context_type not in ("business_place", "address_place") or validation["status"] == "Review",
        "duplicate_found": validation["exists_in_atm_leads"],
        "workflow_state": validation["workflow_state"],
        "existing_lead_name": validation["existing_lead_name"],
        "existing_route": validation["open_existing_lead_url"],
        "open_existing_lead_url": validation["open_existing_lead_url"],
        "prefill": prefill,
        "route": open_url,
        "open_url": open_url,
        "crm_base_url": _crm_base_url(),
        "warnings": warnings,
        "hints": {
            "zone_color": validation["zone_color"],
            "zip_score": validation["zip_score"],
            "status": validation["status"],
            "competitor_count": validation["competitor_count"],
        },
    }
    if validation["exists_in_atm_leads"]:
        message["warning"] = warnings[-1]
    elif not can_create_lead:
        message["warning"] = warnings[0]

    return {
        "message": message,
        "open_url": open_url,
        "crm_base_url": _crm_base_url(),
        "warning": message.get("warning"),
        "route": open_url,
        "prefill": prefill,
        "duplicate_found": validation["exists_in_atm_leads"],
        "existing_lead_name": validation["existing_lead_name"],
        "workflow_state": validation["workflow_state"],
        "existing_route": validation["open_existing_lead_url"],
    }


@frappe.whitelist()
def sync_zip_cache_scope(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    zip_code = _normalize_zip(data.get("zip_code"))
    state = data.get("state") or data.get("state_code")
    row = _zip_row(zip_code=zip_code, state=state)
    if not row:
        return {"message": {"zips": []}, "zips": []}

    zips = [
        {
            "zip_code": row.get("zip_code"),
            "city": row.get("city"),
            "state": row.get("state_code"),
            "zone_color": row.get("zone_color"),
            "zip_score": row.get("zip_score"),
            "competitor_count": _zip_summary(row)["competitor_count"],
            "our_lead_count": row.get("company_kiosks") or 0,
            "validation_status": row.get("location_flag") or "",
        }
    ]
    return {"message": {"zips": zips}, "zips": zips}


@frappe.whitelist()
def sync_lead_cache_scope(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    zip_code = _normalize_zip(data.get("zip_code"))
    filters = {"zip_code": zip_code} if zip_code else {}
    state = data.get("state") or data.get("state_code")
    if state and not zip_code:
        filters["state"] = state

    rows = frappe.get_all(
        "ATM Leads",
        filters=filters,
        fields=["name", "business_name", "address", "zip_code", "state", "state_code", "latitude", "longitude", "workflow_state", "modified"],
        limit_page_length=100,
        order_by="modified desc",
    )
    leads = []
    for row in rows:
        leads.append(
            {
                "atm_lead_name": row.get("name"),
                "business_name": row.get("business_name"),
                "address": row.get("address"),
                "zip_code": row.get("zip_code"),
                "state": row.get("state_code") or row.get("state"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "workflow_state": row.get("workflow_state"),
                "modified": row.get("modified"),
            }
        )
    return {"message": {"leads": leads}, "leads": leads}


@frappe.whitelist()
def sync_competitor_cache_scope(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    zip_code = _normalize_zip(data.get("zip_code"))
    filters = {"actual_zip_code": zip_code} if zip_code else {}
    state = data.get("state") or data.get("state_code")
    if state and not zip_code:
        filters["state_code"] = state

    rows = frappe.get_all(
        "Competitor Kiosk",
        filters=filters,
        fields=["name", "place_id", "display_name", "address", "actual_zip_code", "state_code", "latitude", "longitude", "source", "provider"],
        limit_page_length=100,
        order_by="modified desc",
    )
    competitors = []
    for row in rows:
        competitors.append(
            {
                "external_id": row.get("place_id"),
                "name": row.get("display_name"),
                "address": row.get("address"),
                "zip_code": row.get("actual_zip_code"),
                "state": row.get("state_code"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "source_url": row.get("source"),
                "source_type": row.get("provider"),
                "synced_to_crm": True,
                "crm_competitor_kiosk_name": row.get("name"),
            }
        )
    return {"message": {"competitors": competitors}, "competitors": competitors}


@frappe.whitelist()
def validate_location_scope(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    context_type = _classify_context(data)
    prefill = _prefill_values(data)
    zip_row = _zip_row(zip_code=prefill.get("zip_code"), state=prefill.get("state"))
    lead_match = _lead_matches(data)
    competitor_match = _competitor_match(data)
    message = _validation_message(zip_row, lead_match, competitor_match, context_type=context_type)
    message["context_type"] = context_type
    return {
        "message": message,
        "allowed": message["allowed"],
        "status": message["status"],
        "zone_color": message["zone_color"],
        "zip_score": message["zip_score"],
        "duplicate_found": message["exists_in_atm_leads"],
        "workflow_state": message["workflow_state"],
        "existing_lead_name": message["existing_lead_name"],
        "reason": message["duplicate_reason"],
        "recommended_action": message["recommendation"],
        "competitor_count": message["competitor_count"],
    }


@frappe.whitelist()
def upsert_competitor_kiosk(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    created = upsert_competitor_kiosk_from_radar(
        place_id=_clip(data.get("place_id") or data.get("external_id")),
        display_name=_clip(data.get("name") or data.get("display_name")),
        address=_clip(data.get("address")),
        city=_clip(data.get("city")),
        state_code=_clip(data.get("state") or data.get("state_code")),
        zip_code=data.get("zip_code"),
        actual_zip_code=data.get("zip_code"),
        country=data.get("country") or "United States",
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        source=_clip(data.get("source_url")),
        provider=_clip(data.get("source_type") or "google_maps"),
        brand=_clip(data.get("brand") or "Unknown"),
    )
    message = {
        "status": "created" if created.get("created", False) else "upserted",
        "competitor_kiosk_name": created.get("name"),
        "dedup_reason": "" if created.get("created", False) else "Existing competitor kiosk matched by place, address, name+zip, or nearby coordinates",
    }
    return {
        "message": message,
        "name": created.get("name"),
        "created": created.get("created", False),
        "duplicate": not created.get("created", False),
    }


@frappe.whitelist()
def get_browser_notifications(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    employee = data.get("employee")
    user = frappe.db.get_value("Employee", employee, "user_id") if employee else frappe.session.user
    if not user or user == "Guest":
        return {"message": []}

    rows = frappe.get_all(
        "Notification Log",
        filters={"for_user": user, "read": 0},
        fields=["name", "subject", "email_content", "document_type", "document_name", "creation"],
        order_by="creation desc",
        limit_page_length=10,
    )
    notifications = []
    for row in rows:
        notifications.append(
            {
                "notification_id": row.get("name"),
                "title": row.get("subject") or "CRM Notification",
                "message": frappe.safe_decode(row.get("email_content") or row.get("subject") or "").strip()[:280],
                "created_at": row.get("creation"),
                "document_type": row.get("document_type"),
                "document_name": row.get("document_name"),
            }
        )
    return {"message": notifications}


@frappe.whitelist()
def ack_browser_notification(notification_id=None, payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    target_notification = notification_id or data.get("notification_id")
    if not target_notification:
        return {"message": {"ok": False, "reason": "missing_notification_id"}}

    if frappe.db.exists("Notification Log", target_notification):
        frappe.db.set_value("Notification Log", target_notification, {"read": 1, "seen": 1}, update_modified=False)
    return {
        "message": {
            "ok": True,
            "notification_id": target_notification,
            "acked_at": str(now_datetime()),
        }
    }
