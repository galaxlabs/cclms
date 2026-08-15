import json
from datetime import timedelta
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime
from frappe.utils.file_manager import save_file

from cclms.api import browser_extension


AUTHORIZED_DOMAINS = [
    "crm.galaxylabs.online",
    "mail.google.com",
    "docs.google.com",
    "sheets.google.com",
    "drive.google.com",
    "google.com",
    "maps.google.com",
]
CALL_PROCESS_HINTS = ["ringcentral", "zoiper", "teams", "softphone", "dialer", "phone"]
DEFAULT_CALL_DETAIL_PATTERNS = [
    {
        "name": "phone_number",
        "pattern": r"(\+?\d[\d\s\-\(\)]{6,}\d)",
    }
]
DEFAULT_COMPETITOR_KEYWORDS = ["atm", "bitcoin atm", "crypto kiosk", "coinhub", "coinflip"]


def _loads_payload(payload):
    if isinstance(payload, dict):
        return payload
    if not payload:
        return {}
    return json.loads(payload)


def _clip(value, length=140):
    if value in (None, ""):
        return value
    value = str(value)
    return value[:length]


def _safe_json(value, default=None):
    if value in (None, ""):
        return default if default is not None else {}
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default if default is not None else {}


def _config_bool(key, default=False):
    value = frappe.conf.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _config_int(key, default):
    value = frappe.conf.get(key, default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _resolve_employee(employee=None, user=None):
    if employee:
        return employee
    if user:
        return frappe.db.get_value("Employee", {"user_id": user}, "name")
    return None


def _resolve_sales_agent(user=None, employee=None):
    if user and frappe.db.exists("DocType", "Sales Agent"):
        meta = frappe.get_meta("Sales Agent")
        fieldnames = {field.fieldname for field in meta.fields}
        if "user" in fieldnames:
            name = frappe.db.get_value("Sales Agent", {"user": user}, "name")
            if name:
                return name
        if "email" in fieldnames:
            name = frappe.db.get_value("Sales Agent", {"email": user}, "name")
            if name:
                return name
        if employee and "employee" in fieldnames:
            return frappe.db.get_value("Sales Agent", {"employee": employee}, "name")
    return None


def _require_tracker_service_user():
    roles = set(frappe.get_roles(frappe.session.user))
    if "System Manager" in roles or "Tracker Agent" in roles:
        return
    frappe.throw(_("Tracker service access is not allowed for this user"), frappe.PermissionError)


def _resolve_tracker_binding(data):
    _require_tracker_service_user()

    system_info = data.get("system_info") or {}
    device_id = (
        data.get("device_id")
        or system_info.get("device_id")
        or data.get("machine_name")
        or system_info.get("machine_name")
    )
    if not device_id:
        frappe.throw(_("Device ID is required"))

    tracker = frappe.db.get_value("Tracker Device", {"device_id": device_id}, "*", as_dict=True)
    if not tracker:
        frappe.throw(_("Tracker Device is not enrolled for this laptop"), frappe.PermissionError)
    if int(tracker.active or 0) != 1:
        frappe.throw(_("Tracker Device is inactive"), frappe.PermissionError)

    allowed_service_user = (tracker.allowed_service_user or "").strip()
    if allowed_service_user and frappe.session.user != allowed_service_user and "System Manager" not in frappe.get_roles():
        frappe.throw(_("This service user is not allowed for the selected device"), frappe.PermissionError)

    payload_user = (data.get("user") or "").strip()
    if payload_user and tracker.tracked_user and payload_user != tracker.tracked_user:
        frappe.throw(_("Payload user does not match enrolled tracker user"), frappe.PermissionError)

    payload_employee = (data.get("employee") or "").strip()
    if payload_employee and tracker.employee and payload_employee != tracker.employee:
        frappe.throw(_("Payload employee does not match enrolled tracker employee"), frappe.PermissionError)

    frappe.db.set_value(
        "Tracker Device",
        tracker.name,
        {
            "machine_name": system_info.get("machine_name") or data.get("machine_name") or tracker.machine_name,
            "ip_address": system_info.get("ip_address") or tracker.ip_address,
            "last_seen_on": now_datetime(),
        },
        update_modified=False,
    )
    # Resolve sales agent: prefer the explicit Tracker Device field, then derive.
    sales_agent = (tracker.get("sales_agent") or "").strip() or _resolve_sales_agent(
        user=tracker.tracked_user,
        employee=tracker.employee or _resolve_employee(user=tracker.tracked_user),
    )
    _sync_device_profile(
        device_id=device_id,
        user=tracker.tracked_user,
        employee=tracker.employee or _resolve_employee(user=tracker.tracked_user),
        sales_agent=sales_agent,
        system_info=system_info,
    )
    return {
        "tracker_name": tracker.name,
        "device_id": device_id,
        "tracked_user": tracker.tracked_user,
        "employee": tracker.employee or _resolve_employee(user=tracker.tracked_user),
        "sales_agent": sales_agent,
    }


def _tracker_runtime_policy(binding):
    tracker = frappe.db.get_value("Tracker Device", binding.get("tracker_name"), "*", as_dict=True) or {}
    biometric_enabled = int(tracker.get("biometric_enabled") or 0) == 1
    biometric_device = {
        "enabled": biometric_enabled,
        "ip": tracker.get("biometric_ip"),
        "port": tracker.get("biometric_port") or 4370,
        "password": tracker.get("biometric_password"),
        "device_identifier": tracker.get("biometric_device_identifier"),
        "sync_minutes": tracker.get("biometric_sync_minutes") or 15,
        "last_sync_on": tracker.get("biometric_last_sync_on"),
    } if biometric_enabled else None
    return {
        "productivity_rules": _safe_json(tracker.get("productivity_rules_json"), default=[]),
        "device_actions_enabled": int(tracker.get("device_actions_enabled") or 0) == 1,
        "action_poll_seconds": tracker.get("action_poll_seconds") or 60,
        "device_health_enabled": _config_bool("tracker_device_health_enabled", False),
        "device_health_poll_seconds": _config_int("tracker_device_health_poll_seconds", 300),
        "notifications_enabled": int(tracker.get("notifications_enabled") or 0) == 1
        or _config_bool("tracker_notifications_enabled", True),
        "notifications_poll_seconds": tracker.get("notifications_poll_seconds")
        or _config_int("tracker_notifications_poll_seconds", 60),
        "biometric_device": biometric_device,
        "biometric_sync_enabled": biometric_enabled,
        "biometric_sync_interval_minutes": tracker.get("biometric_sync_minutes") or 15,
        "call_metadata_enabled": _config_bool("tracker_call_metadata_enabled", True),
        "call_detail_patterns": _safe_json(frappe.conf.get("tracker_call_detail_patterns"), default=DEFAULT_CALL_DETAIL_PATTERNS),
        "map_intelligence_enabled": _config_bool("tracker_map_intelligence_enabled", False),
        "map_sync_scope_seconds": _config_int("tracker_map_sync_scope_seconds", 180),
        "map_context_debounce_seconds": _config_int("tracker_map_context_debounce_seconds", 20),
        "competitor_keywords": _safe_json(frappe.conf.get("tracker_competitor_keywords"), default=DEFAULT_COMPETITOR_KEYWORDS),
        "map_popup_enabled": _config_bool("tracker_map_popup_enabled", True),
        "follow_up_dial_enabled": int(tracker.get("follow_up_dial_enabled", 1) if tracker.get("follow_up_dial_enabled") is not None else 1) == 1,
        "follow_up_dial_start_hour": tracker.get("follow_up_dial_start_hour") or 9,
        "follow_up_dial_end_hour": tracker.get("follow_up_dial_end_hour") or 21,
        "follow_up_dial_timezone": tracker.get("follow_up_dial_timezone") or "",
    }


def _sync_device_profile(device_id, user=None, employee=None, sales_agent=None, system_info=None):
    if not device_id or not frappe.db.exists("DocType", "Device Profile"):
        return

    system_info = system_info or {}
    profile_name = frappe.db.get_value("Device Profile", {"device_id": device_id}, "name")
    if not profile_name:
        return

    values = {
        "tracked_user": user,
        "employee": employee,
        "sales_agent": sales_agent,
        "machine_name": system_info.get("machine_name"),
        "windows_username": system_info.get("windows_username") or system_info.get("username"),
        "ip_address": system_info.get("ip_address"),
        "last_seen_on": now_datetime(),
    }
    cleaned = {key: value for key, value in values.items() if value not in (None, "")}
    if cleaned:
        frappe.db.set_value("Device Profile", profile_name, cleaned, update_modified=False)


def _site_domain_list():
    domains = frappe.conf.get("tracker_allowed_domains")
    if isinstance(domains, (list, tuple)) and domains:
        return [str(value).strip().lower() for value in domains if str(value).strip()]
    return AUTHORIZED_DOMAINS


def _is_authorized_url(url):
    if not url:
        return 1
    domain = (urlparse(url).netloc or "").lower().strip()
    if not domain:
        return 1
    for allowed in _site_domain_list():
        if domain == allowed or domain.endswith(f".{allowed}"):
            return 1
    return 0


def _save_base64_image(base64_str, employee_id, session_name):
    if not base64_str:
        return None
    if "," in base64_str:
        base64_str = base64_str.split(",", 1)[1]

    filename = f"snap_{employee_id}_{frappe.generate_hash(length=8)}.jpg"
    file_doc = save_file(
        filename,
        base64_str,
        "Employee Activity Log",
        session_name,
        is_private=1,
        decode=True,
    )
    return file_doc.file_url


def _normalize_call_direction(value):
    direction = (value or "").strip().lower()
    if direction == "incoming":
        return "Inbound"
    if direction == "outgoing":
        return "Outbound"
    if direction in {"inbound", "outbound"}:
        return direction.title()
    return value


def _get_or_create_daily_log(employee=None, user=None, event_time=None, system_info=None):
    event_dt = get_datetime(event_time) if event_time else now_datetime()
    employee = _resolve_employee(employee=employee, user=user)

    filters = {"date": str(event_dt.date())}
    if employee:
        filters["employee"] = employee
    elif user:
        filters["user"] = user
    else:
        frappe.throw("Employee or user is required")

    existing = frappe.db.get_value("Employee Activity Log", filters, "name")
    if existing:
        return frappe.get_doc("Employee Activity Log", existing)

    doc = frappe.get_doc(
        {
            "doctype": "Employee Activity Log",
            "employee": employee,
            "user": user,
            "sales_agent": _resolve_sales_agent(user=user, employee=employee),
            "date": str(event_dt.date()),
            "login_time": event_dt,
            "last_heartbeat": event_dt,
            "status": "Active",
            "system_info_json": frappe.as_json(system_info or {}, indent=2),
        }
    )
    if isinstance(system_info, dict):
        doc.device_id = system_info.get("device_id")
        doc.machine_name = system_info.get("machine_name")
        doc.ip_address = system_info.get("ip_address")
    doc.insert(ignore_permissions=True)
    return doc


def _append_activity_row(log_doc, payload, screenshot_url=None):
    website_url = payload.get("website_url") or ""
    domain = (urlparse(website_url).netloc or "").lower().strip() if website_url else ""
    event_type = payload.get("event_type") or "Heartbeat"
    idle_seconds = int(payload.get("idle_seconds") or 0)
    system_awake = payload.get("system_awake", True)
    event_minutes = payload.get("event_minutes") or 0
    # Classify event as idle when user input stopped for the threshold
    idle_threshold = int(frappe.conf.get("tracker_idle_threshold_seconds") or 120)
    is_idle_event = idle_seconds > idle_threshold or not system_awake
    row = {
        "event_time": get_datetime(payload.get("event_time")) if payload.get("event_time") else now_datetime(),
        "event_type": _clip(event_type),
        "event_source": _clip(payload.get("event_source") or "windows-agent"),
        "active_app": _clip(payload.get("active_app")),
        "window_title": _clip(payload.get("window_title")),
        "website_url": _clip(website_url),
        "domain": _clip(domain),
        "productivity_rating": _clip(payload.get("productivity_rating")),
        "productivity_score": payload.get("productivity_score"),
        "productivity_rule_name": _clip(payload.get("productivity_rule_name")),
        "is_authorized": _is_authorized_url(website_url),
        "event_minutes": event_minutes,
        "idle_seconds": idle_seconds,
        "system_awake": 1 if system_awake else 0,
        "call_start": payload.get("call_start"),
        "call_end": payload.get("call_end"),
        "reference_id": _clip(payload.get("reference_id") or payload.get("call_id")),
        "screenshot": screenshot_url,
        "summary": payload.get("summary"),
    }
    log_doc.append("activity_logs", row)

    # Roll up active/idle minutes on the daily log from a 9-hour workday baseline.
    _rollup_daily_active_minutes(log_doc, row, is_idle_event, event_minutes)


def _rollup_daily_active_minutes(log_doc, row, is_idle_event, event_minutes):
    """
    Track active vs idle minutes on the Employee Activity Log.

    Baseline: a 9-hour workday (540 minutes). Breaks, lunch and party/off time are
    NOT counted as active. Active minutes accumulate from non-idle events; idle
    minutes accumulate when the user was away (idle threshold exceeded or system
    asleep/locked).
    """
    try:
        minutes = float(event_minutes or 0)
        if minutes <= 0:
            return
        active = 0.0
        idle = 0.0
        if is_idle_event:
            idle = minutes
        else:
            active = minutes

        total_active = float(log_doc.get("total_active_minutes") or 0) + active
        total_idle = float(log_doc.get("total_idle_minutes") or 0) + idle

        # Cap net productive time at the 9-hour workday baseline.
        workday_minutes = int(frappe.conf.get("tracker_workday_minutes") or 540)
        if total_active > workday_minutes:
            total_active = float(workday_minutes)

        log_doc.set("total_active_minutes", round(total_active, 2))
        log_doc.set("total_idle_minutes", round(total_idle, 2))
        if is_idle_event and row.get("event_type") == "Heartbeat":
            log_doc.set("status", "Idle")
        elif log_doc.get("status") != "Logged Out":
            log_doc.set("status", "Active")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Tracker idle rollup failed")


def _upsert_call_daily_summary(call_doc):
    if not frappe.db.exists("DocType", "Call Daily Summary"):
        return None

    summary_name = frappe.db.get_value(
        "Call Daily Summary",
        {"employee": call_doc.employee, "date": call_doc.call_date},
        "name",
    )
    if summary_name:
        summary = frappe.get_doc("Call Daily Summary", summary_name)
    else:
        summary = frappe.get_doc(
            {
                "doctype": "Call Daily Summary",
                "employee": call_doc.employee,
                "user": call_doc.user,
                "sales_agent": call_doc.sales_agent,
                "date": call_doc.call_date,
                "status": "Open",
            }
        )
        summary.insert(ignore_permissions=True)

    rows = frappe.get_all(
        "Call Detail",
        fields=["duration", "status"],
        filters={"employee": call_doc.employee, "call_date": call_doc.call_date},
        limit_page_length=5000,
    )

    total_calls = len(rows)
    answered_calls = sum(1 for row in rows if row.status in ("Completed", "Started"))
    missed_calls = sum(1 for row in rows if row.status == "Missed")
    rejected_calls = sum(1 for row in rows if row.status == "Rejected")
    durations = [int(row.duration or 0) for row in rows]
    total_seconds = sum(durations)

    frappe.db.set_value(
        "Call Daily Summary",
        summary.name,
        {
            "sales_agent": call_doc.sales_agent,
            "total_calls": total_calls,
            "answered_calls": answered_calls,
            "missed_calls": missed_calls,
            "rejected_calls": rejected_calls,
            "total_talk_time_seconds": total_seconds,
            "average_call_seconds": round(total_seconds / total_calls, 2) if total_calls else 0,
            "longest_call_seconds": max(durations) if durations else 0,
            "last_synced_on": now_datetime(),
        },
        update_modified=False,
    )
    return summary.name


@frappe.whitelist(allow_guest=False)
def get_tracking_policy(payload=None):
    _require_tracker_service_user()
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data) if data else None
    runtime_policy = _tracker_runtime_policy(binding) if binding else {}
    return {
        "allowed_domains": _site_domain_list(),
        "call_process_hints": CALL_PROCESS_HINTS,
        "snapshot_min_minutes": 45,
        "snapshot_max_minutes": 75,
        "heartbeat_seconds": 60,
        "productivity_rules": runtime_policy.get("productivity_rules") or [],
        "device_actions_enabled": runtime_policy.get("device_actions_enabled") or False,
        "action_poll_seconds": runtime_policy.get("action_poll_seconds") or 60,
        "device_actions_poll_seconds": runtime_policy.get("action_poll_seconds") or 60,
        "device_health_enabled": runtime_policy.get("device_health_enabled") or False,
        "device_health_poll_seconds": runtime_policy.get("device_health_poll_seconds") or 300,
        "notifications_enabled": runtime_policy.get("notifications_enabled") or False,
        "notifications_poll_seconds": runtime_policy.get("notifications_poll_seconds") or 60,
        "biometric_device": runtime_policy.get("biometric_device"),
        "biometric_sync_enabled": runtime_policy.get("biometric_sync_enabled") or False,
        "biometric_sync_interval_minutes": runtime_policy.get("biometric_sync_interval_minutes") or 15,
        "call_metadata_enabled": runtime_policy.get("call_metadata_enabled", True),
        "call_detail_patterns": runtime_policy.get("call_detail_patterns") or DEFAULT_CALL_DETAIL_PATTERNS,
        "map_intelligence_enabled": runtime_policy.get("map_intelligence_enabled") or False,
        "map_sync_scope_seconds": runtime_policy.get("map_sync_scope_seconds") or 180,
        "map_context_debounce_seconds": runtime_policy.get("map_context_debounce_seconds") or 20,
        "competitor_keywords": runtime_policy.get("competitor_keywords") or DEFAULT_COMPETITOR_KEYWORDS,
        "map_popup_enabled": runtime_policy.get("map_popup_enabled", True),
        "binding": {
            "tracker_device": binding.get("tracker_name"),
            "device_id": binding.get("device_id"),
            "tracked_user": binding.get("tracked_user"),
            "employee": binding.get("employee"),
            "sales_agent": binding.get("sales_agent"),
        } if binding else None,
    }


def _extension_payload(data, binding=None):
    binding = binding or {}
    return {
        "place": {
            "source_url": data.get("url") or data.get("source_url"),
            "source_type": data.get("source_type"),
            "name": data.get("place_name") or data.get("name") or data.get("business_name"),
            "address": data.get("address"),
            "phone": data.get("phone"),
            "website": data.get("website"),
            "category": data.get("category") or data.get("business_type"),
            "coordinates": {
                "lat": data.get("latitude"),
                "lng": data.get("longitude"),
            },
            "zip_code": data.get("zip_code"),
            "city": data.get("city"),
            "state": data.get("state"),
            "place_fingerprint": data.get("fingerprint"),
        },
        "device_id": binding.get("device_id") or data.get("device_id"),
        "employee": binding.get("employee") or data.get("employee"),
        "source_system": data.get("source_system"),
        "browser_context": data.get("browser_context") or {"source": data.get("source_type") or "windows_tracker"},
    }


@frappe.whitelist(allow_guest=False)
def report_device_health(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    system_info = data.get("system_info") or {}

    if frappe.db.exists("DocType", "Tracker Device Health Log"):
        health_doc = frappe.get_doc(
            {
                "doctype": "Tracker Device Health Log",
                "device_id": binding.get("device_id"),
                "tracker_device": binding.get("tracker_name"),
                "tracked_user": binding.get("tracked_user"),
                "employee": binding.get("employee"),
                "sales_agent": binding.get("sales_agent"),
                "machine_name": data.get("machine_name") or system_info.get("machine_name"),
                "windows_username": data.get("windows_username") or system_info.get("windows_username") or system_info.get("username"),
                "version": _clip(data.get("version"), length=140),
                "queue_count": int(data.get("queue_count") or 0),
                "process_count": int(data.get("process_count") or 0),
                "dns_ok": 1 if (data.get("dns_status") or {}).get("ok") else 0,
                "dns_host": _clip((data.get("dns_status") or {}).get("host"), length=255),
                "dns_ip": _clip((data.get("dns_status") or {}).get("ip"), length=255),
                "dns_error": _clip((data.get("dns_status") or {}).get("error"), length=1000),
                "report_time": get_datetime(data.get("time_utc")) if data.get("time_utc") else now_datetime(),
                "last_log_lines_json": frappe.as_json(data.get("last_log_lines") or [], indent=2),
                "processes_json": frappe.as_json(data.get("processes") or [], indent=2),
                "system_info_json": frappe.as_json(system_info, indent=2),
                "raw_payload_json": frappe.as_json(data, indent=2),
            }
        )
        health_doc.insert(ignore_permissions=True)

    _sync_device_profile(
        device_id=binding.get("device_id"),
        user=binding.get("tracked_user"),
        employee=binding.get("employee"),
        sales_agent=binding.get("sales_agent"),
        system_info={
            **system_info,
            "machine_name": data.get("machine_name") or system_info.get("machine_name"),
            "windows_username": data.get("windows_username") or system_info.get("windows_username") or system_info.get("username"),
        },
    )

    # Denormalize latest health snapshot onto Tracker Device for fleet dashboards
    tracker_name = binding.get("tracker_name")
    if tracker_name and frappe.db.exists("Tracker Device", tracker_name):
        dns = data.get("dns_status") or {}
        frappe.db.set_value(
            "Tracker Device",
            tracker_name,
            {
                "latest_app_version": _clip(data.get("version"), length=140),
                "latest_health_report_at": get_datetime(data.get("time_utc")) if data.get("time_utc") else now_datetime(),
                "latest_queue_count": int(data.get("queue_count") or 0),
                "latest_tracker_process_count": int(data.get("process_count") or 0),
                "latest_dns_ok": 1 if dns.get("ok") else 0,
                "latest_dns_ip": _clip(dns.get("ip"), length=255),
                "latest_memory_percent": float((system_info or {}).get("memory_percent") or 0),
                "latest_cpu_percent": float((system_info or {}).get("cpu_percent") or 0),
                "latest_log_excerpt": _clip((data.get("last_log_lines") or [""])[-1] if data.get("last_log_lines") else "", length=1400),
                "device_health_status": _classify_device_health(data),
            },
            update_modified=False,
        )

    frappe.db.commit()
    return {"message": {"ok": True, "device_id": binding.get("device_id"), "received_at": str(now_datetime())}}


def _classify_device_health(data):
    """Classify a device as Healthy / Warning / Offline / Error per BACKEND_LOGIC_SPEC 6.1."""
    queue_count = int(data.get("queue_count") or 0)
    process_count = int(data.get("process_count") or 0)
    dns_ok = bool((data.get("dns_status") or {}).get("ok"))
    system_info = data.get("system_info") or {}
    memory = float(system_info.get("memory_percent") or 0)
    if not dns_ok:
        return "Error"
    if queue_count > 0 or process_count > 1 or memory > 85:
        return "Warning"
    return "Healthy"


@frappe.whitelist(allow_guest=False)
def ingest_activity(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    event_time = data.get("event_time")
    user = binding.get("tracked_user")
    employee = binding.get("employee")
    system_info = data.get("system_info") or {}
    log_doc = _get_or_create_daily_log(employee=employee, user=user, event_time=event_time, system_info=system_info)

    screenshot_url = None
    if data.get("screenshot_base64"):
        screenshot_url = _save_base64_image(data.get("screenshot_base64"), employee or user, log_doc.name)

    _append_activity_row(log_doc, data, screenshot_url=screenshot_url)

    updates = {
        "last_heartbeat": get_datetime(event_time) if event_time else now_datetime(),
        "active_app": data.get("active_app") or log_doc.active_app,
        "activity_type": data.get("activity_type") or log_doc.activity_type,
        "sales_agent": binding.get("sales_agent") or getattr(log_doc, "sales_agent", None),
        "machine_name": system_info.get("machine_name") or log_doc.machine_name,
        "device_id": binding.get("device_id") or system_info.get("device_id") or log_doc.device_id,
        "ip_address": system_info.get("ip_address") or log_doc.ip_address,
        "status": "Active" if (data.get("event_type") or "").lower() != "idle" else "Idle",
    }
    if data.get("event_type") == "Login" and not log_doc.login_time:
        updates["login_time"] = updates["last_heartbeat"]
    if system_info:
        updates["system_info_json"] = frappe.as_json(system_info, indent=2)

    for fieldname, value in updates.items():
        if value not in (None, ""):
            log_doc.set(fieldname, value)

    log_doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "activity_log": log_doc.name}


@frappe.whitelist(allow_guest=False)
def get_device_actions(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    runtime_policy = _tracker_runtime_policy(binding)
    if not runtime_policy.get("device_actions_enabled"):
        return {"message": []}

    now = now_datetime()
    actions = frappe.get_all(
        "Tracker Device Action",
        fields=[
            "name",
            "device_id",
            "action_type",
            "payload_json",
            "expires_at",
            "approved_by",
            "created_at",
            "status",
        ],
        filters={"device_id": binding.get("device_id"), "status": "pending"},
        order_by="creation asc",
        limit_page_length=20,
    )
    output = []
    for action in actions:
        expires_at = action.get("expires_at")
        if expires_at and get_datetime(expires_at) < now:
            frappe.db.set_value(
                "Tracker Device Action",
                action["name"],
                {"status": "expired", "completed_at": now},
                update_modified=False,
            )
            continue
        output.append(
            {
                "action_id": action["name"],
                "device_id": action["device_id"],
                "action_type": action["action_type"],
                "payload": _safe_json(action.get("payload_json"), default={}),
                "expires_at": action.get("expires_at"),
                "approved_by": action.get("approved_by"),
                "created_at": action.get("created_at"),
                "status": action.get("status"),
            }
        )
    return {"message": output}


@frappe.whitelist(allow_guest=False)
def update_device_action_status(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    action_id = data.get("action_id")
    if not action_id:
        frappe.throw(_("Action ID is required"))

    action = frappe.get_doc("Tracker Device Action", action_id)
    if action.device_id != binding.get("device_id"):
        frappe.throw(_("Action does not belong to this device"), frappe.PermissionError)

    status = (data.get("status") or "").strip().lower()
    if status not in {"running", "success", "failed", "expired"}:
        frappe.throw(_("Invalid action status"))

    updates = {
        "status": status,
        "result_json": frappe.as_json(data.get("result") or {}, indent=2),
        "error_message": _clip(data.get("error_message"), length=1000),
    }
    if status == "running":
        updates["started_at"] = now_datetime()
    if status in {"success", "failed", "expired"}:
        updates["completed_at"] = now_datetime()
    frappe.db.set_value("Tracker Device Action", action.name, updates, update_modified=False)
    frappe.db.commit()
    return {"ok": True, "action_id": action.name, "status": status}


@frappe.whitelist(allow_guest=False)
def ack_device_action(payload=None):
    data = _loads_payload(payload)
    data["result"] = {"message": data.get("message")} if data.get("message") else (data.get("result") or {})
    return update_device_action_status(payload=data)


@frappe.whitelist(allow_guest=False)
def get_device_notifications(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    notifications = []

    rows = frappe.get_all(
        "Notification Log",
        filters={"for_user": binding.get("tracked_user"), "read": 0},
        fields=["name", "subject", "email_content", "creation", "document_type", "document_name", "type"],
        order_by="creation desc",
        limit_page_length=10,
    )
    for row in rows:
        body = frappe.safe_decode(row.get("email_content") or row.get("subject") or "").strip()[:280]
        notifications.append(
            {
                "notification_id": row.get("name"),
                "enabled": True,
                "title": row.get("subject") or "CRM Notification",
                "message": body,
                "body": body,
                "repeat_seconds": 300,
                "severity": "info",
                "type": row.get("type") or "Alert",
                "document_type": row.get("document_type"),
                "document_name": row.get("document_name"),
                "route": ["Form", row.get("document_type"), row.get("document_name")]
                if row.get("document_type") and row.get("document_name")
                else None,
                "created_on": str(row.get("creation") or ""),
            }
        )

    recent_failures = frappe.get_all(
        "Tracker Device Action",
        filters={"device_id": binding.get("device_id"), "status": "failed"},
        fields=["name", "action_type", "error_message"],
        order_by="modified desc",
        limit_page_length=3,
    )
    for row in recent_failures:
        notifications.append(
            {
                "notification_id": f"action-failed-{row.get('name')}",
                "enabled": True,
                "title": "Device Action Failed",
                "message": f"{row.get('action_type')}: {_clip(row.get('error_message'), length=180) or 'Unknown error'}",
                "repeat_seconds": 900,
                "severity": "warning",
            }
        )

    # --- Tracked user's own ATM Leads status changes -------------------------
    # Notify the laptop owner about leads assigned to their Sales Agent that
    # were recently Approved / Rejected / Signed / Signed Rejected / Installed.
    lead_notifications = _atm_lead_status_notifications(binding)
    notifications.extend(lead_notifications)

    return {"message": notifications}


def _atm_lead_status_notifications(binding, since_minutes=1440):
    """Return recent workflow-state changes on the tracked user's own ATM Leads.

    Matches leads where ANY of the following point at the tracked user:
      - executive_name == the device's Sales Agent
      - lead_owner == the user's full name
      - owner       == the user email (CRM document owner)
    """
    agent = binding.get("sales_agent")
    tracked_user = binding.get("tracked_user")
    if not agent and not tracked_user:
        return []

    notify_states = {
        "Approved": ("Approved", "green"),
        "Rejected": ("Rejected", "red"),
        "Installed": ("Installed", "teal"),
    }

    base = [["workflow_state", "in", list(notify_states)], ["modified", ">=", add_to_date(now_datetime(), minutes=-since_minutes)]]

    # Build a set of unique lead names matched by any of the three paths.
    match_names = set()
    candidate_filters = []
    if agent:
        candidate_filters.append(base + [["executive_name", "=", agent]])
    if tracked_user:
        full_name = frappe.db.get_value("User", tracked_user, "full_name")
        if full_name:
            candidate_filters.append(base + [["lead_owner", "=", full_name]])
        candidate_filters.append(base + [["owner", "=", tracked_user]])

    for filters in candidate_filters:
        names = frappe.get_all("ATM Leads", filters=filters, pluck="name", limit_page_length=15)
        match_names.update(names)

    if not match_names:
        return []

    rows = frappe.get_all(
        "ATM Leads",
        filters=[["name", "in", list(match_names)]],
        fields=["name", "business_name", "workflow_state", "city", "state", "modified", "post_date"],
        order_by="modified desc",
        limit_page_length=15,
    )

    notifications = []
    for row in rows:
        state, indicator = notify_states[row["workflow_state"]]
        title = f"ATM Lead {state}"
        location = " ".join(filter(None, [row.get("business_name"), row.get("city"), row.get("state")])).strip() or row["name"]
        notifications.append(
            {
                "notification_id": f"atm-lead-{row['name']}-{state}",
                "enabled": True,
                "title": title,
                "message": f"{location} → {state}",
                "body": f"{location}\nStatus: {state}",
                "repeat_seconds": 3600,
                "severity": "warning" if indicator == "red" else "info",
                "type": "ATM Lead",
                "document_type": "ATM Leads",
                "document_name": row["name"],
                "route": ["Form", "ATM Leads", row["name"]],
                "changed_on": str(row.get("modified") or ""),
            }
        )
    return notifications


@frappe.whitelist(allow_guest=False)
def ingest_biometric_attendance(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    runtime_policy = _tracker_runtime_policy(binding)
    biometric_device = runtime_policy.get("biometric_device") or {}
    request_biometric = data.get("biometric_device") or {}
    if request_biometric and not biometric_device:
        biometric_device = request_biometric
    rows = data.get("attendance_logs") or data.get("records") or []
    if not rows:
        return {"ok": True, "inserted": 0}

    inserted = 0
    for row in rows:
        row = row or {}
        timestamp = row.get("attendance_time") or row.get("timestamp")
        log_doc = frappe.get_doc(
            {
                "doctype": "Tracker Biometric Attendance Log",
                "device_id": binding.get("device_id"),
                "tracker_device": binding.get("tracker_name"),
                "biometric_device_identifier": biometric_device.get("device_identifier") or row.get("device_identifier"),
                "biometric_user_id": row.get("biometric_user_id") or row.get("user_id") or row.get("uid"),
                "attendance_time": get_datetime(timestamp) if timestamp else None,
                "punch_state": row.get("punch_state") or row.get("status") or row.get("punch"),
                "employee": binding.get("employee"),
                "user": binding.get("tracked_user"),
                "raw_payload_json": frappe.as_json(row, indent=2),
            }
        )
        log_doc.insert(ignore_permissions=True)
        inserted += 1

        if frappe.db.exists("DocType", "Employee Checkin") and binding.get("employee") and timestamp:
            exists = frappe.db.exists(
                "Employee Checkin",
                {"employee": binding.get("employee"), "time": get_datetime(timestamp)},
            )
            if not exists:
                frappe.get_doc(
                    {
                        "doctype": "Employee Checkin",
                        "employee": binding.get("employee"),
                        "time": get_datetime(timestamp),
                        "log_type": "IN" if (row.get("punch_state") or "").upper() not in {"OUT", "CHECKOUT"} else "OUT",
                        "device_id": biometric_device.get("device_identifier") or binding.get("device_id"),
                    }
                ).insert(ignore_permissions=True)

    frappe.db.set_value(
        "Tracker Device",
        binding.get("tracker_name"),
        {"biometric_last_sync_on": now_datetime()},
        update_modified=False,
    )
    frappe.db.commit()
    return {"message": {"accepted": inserted, "duplicates": 0}, "ok": True, "inserted": inserted}


@frappe.whitelist(allow_guest=False)
def sync_zip_cache_scope(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    return browser_extension.sync_zip_cache_scope(payload=_extension_payload(data, binding=binding))


@frappe.whitelist(allow_guest=False)
def sync_lead_cache_scope(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    return browser_extension.sync_lead_cache_scope(payload=_extension_payload(data, binding=binding))


@frappe.whitelist(allow_guest=False)
def sync_competitor_cache_scope(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    return browser_extension.sync_competitor_cache_scope(payload=_extension_payload(data, binding=binding))


@frappe.whitelist(allow_guest=False)
def validate_location_scope(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    return browser_extension.validate_location_scope(payload=_extension_payload(data, binding=binding))


@frappe.whitelist(allow_guest=False)
def upsert_competitor_kiosk(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    response = browser_extension.upsert_competitor_kiosk(payload=_extension_payload(data, binding=binding))
    message = response.get("message") or {}
    normalized = {
        "name": response.get("name") or message.get("competitor_kiosk_name"),
        "created": response.get("created"),
        "duplicate": response.get("duplicate"),
    }
    return {"message": normalized, **normalized}


@frappe.whitelist(allow_guest=False)
def ingest_call(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    user = binding.get("tracked_user")
    employee = binding.get("employee")
    event_dt = get_datetime(data.get("start_time")) if data.get("start_time") else now_datetime()
    log_doc = _get_or_create_daily_log(employee=employee, user=user, event_time=event_dt, system_info=data.get("system_info"))

    call_id = data.get("call_id") or frappe.generate_hash(length=12)
    existing = frappe.db.get_value("Call Detail", {"call_id": call_id}, "name")
    if existing:
        call_doc = frappe.get_doc("Call Detail", existing)
    else:
        call_doc = frappe.new_doc("Call Detail")
        call_doc.call_id = call_id

    call_doc.employee = employee
    call_doc.user = user
    call_doc.sales_agent = binding.get("sales_agent")
    call_doc.activity_log = log_doc.name
    call_doc.call_date = data.get("call_date") or str(event_dt.date())
    call_doc.start_time = data.get("start_time") or call_doc.start_time or event_dt
    call_doc.end_time = data.get("end_time") or call_doc.end_time
    call_doc.status = data.get("status") or call_doc.status or "Completed"
    call_doc.direction = _normalize_call_direction(data.get("direction")) or call_doc.direction or "Outbound"
    call_doc.source_system = data.get("source_system") or data.get("event_source") or "windows-agent"
    call_doc.customer_number = data.get("customer_number") or data.get("phone_number") or data.get("caller_phone") or data.get("callee_phone")
    call_doc.duration = data.get("duration") or data.get("duration_seconds") or call_doc.duration
    call_doc.call_outcome = data.get("call_outcome") or call_doc.call_outcome or None
    call_doc.talk_duration_seconds = int(data.get("talk_duration_seconds") or data.get("duration_seconds") or call_doc.duration or 0)
    call_doc.reference_id = data.get("reference_id") or data.get("ringcentral_call_id") or data.get("call_id") or call_doc.reference_id
    call_doc.sentiment = data.get("sentiment")
    call_doc.client_response = data.get("client_response")
    call_doc.transcript = data.get("transcript")
    call_doc.save(ignore_permissions=True)

    _append_activity_row(
        log_doc,
        {
            "event_time": call_doc.end_time or call_doc.start_time,
            "event_type": "Call",
            "event_source": call_doc.source_system,
            "active_app": data.get("active_app"),
            "window_title": data.get("window_title"),
            "event_minutes": round(int(call_doc.duration or 0) / 60.0, 2),
            "call_start": call_doc.start_time,
            "call_end": call_doc.end_time,
            "call_id": call_doc.call_id,
            "summary": f"{call_doc.status or 'Call'} {call_doc.direction or ''}".strip(),
        },
    )
    log_doc.save(ignore_permissions=True)

    summary_name = _upsert_call_daily_summary(call_doc)
    frappe.db.commit()
    return {"ok": True, "call_detail": call_doc.name, "activity_log": log_doc.name, "daily_summary": summary_name}


@frappe.whitelist(allow_guest=False)
def ingest_call_details(payload=None):
    data = _loads_payload(payload)
    if data.get("duration_seconds") and not data.get("duration"):
        data["duration"] = data.get("duration_seconds")
    if data.get("phone_number") and not data.get("customer_number"):
        data["customer_number"] = data.get("phone_number")
    if not data.get("customer_number"):
        data["customer_number"] = data.get("caller_phone") or data.get("callee_phone")
    return ingest_call(payload=data)


@frappe.whitelist(allow_guest=False)
def ingest_logout(payload=None):
    data = _loads_payload(payload)
    binding = _resolve_tracker_binding(data)
    user = binding.get("tracked_user")
    employee = binding.get("employee")
    log_doc = _get_or_create_daily_log(employee=employee, user=user, event_time=data.get("event_time"), system_info=data.get("system_info"))
    _append_activity_row(log_doc, {"event_type": "Logout", "event_time": data.get("event_time"), "summary": "System logout"})
    log_doc.logout_time = get_datetime(data.get("event_time")) if data.get("event_time") else now_datetime()
    log_doc.last_heartbeat = log_doc.logout_time
    log_doc.status = "Logged Out"
    log_doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "activity_log": log_doc.name}


@frappe.whitelist()
def rebuild_call_daily_summaries(days_back=31):
    days_back = max(1, int(days_back or 31))
    from_date = now_datetime().date() - timedelta(days=days_back)
    rows = frappe.db.sql(
        """
        SELECT DISTINCT employee, call_date
        FROM `tabCall Detail`
        WHERE call_date >= %(from_date)s
          AND IFNULL(employee, '') != ''
        ORDER BY call_date ASC
        """,
        {"from_date": str(from_date)},
        as_dict=True,
    )

    rebuilt = 0
    for row in rows:
        sample = frappe.db.get_value(
            "Call Detail",
            {"employee": row.employee, "call_date": row.call_date},
            "name",
        )
        if not sample:
            continue
        _upsert_call_daily_summary(frappe.get_doc("Call Detail", sample))
        rebuilt += 1

    frappe.db.commit()
    return {"rebuilt": rebuilt, "days_back": days_back}
