"""
Attendance API — Agent Checkin / Checkout & Summary
-----------------------------------------------------
All endpoints are whitelisted and accept POST from the React frontend.

Usage:
  frappe.call("cclms.call_centre_lead_management_system.api.attendance.agent_checkin", {...})
"""

import frappe
from frappe.utils import now_datetime, getdate, today
from datetime import datetime, timedelta

from cclms.call_centre_lead_management_system.doctype.shift_settings.shift_settings import (
    get_active_shift,
)


# ─────────────────────────────────────────────────────────────────────────────
# Check-In
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def agent_checkin(employee: str, shift_settings: str = None, location: str = None):
    """
    Record a check-in for an agent.
    Returns the Agent Checkin document name.

    - Prevents double check-in for the same shift date.
    - Auto-selects the default Shift Settings if not provided.
    """
    if not shift_settings:
        shift = get_active_shift()
        shift_settings = shift.name
    else:
        shift = frappe.get_doc("Shift Settings", shift_settings)

    shift_date = _resolve_shift_date(shift)

    # Prevent double check-in
    existing = frappe.db.get_value(
        "Agent Checkin",
        {"employee": employee, "shift_date": shift_date},
        "name",
    )
    if existing:
        frappe.throw(
            f"Agent {employee} has already checked in for shift date {shift_date} "
            f"(record: {existing}). Use checkout API to check out.",
            title="Already Checked In",
        )

    doc = frappe.new_doc("Agent Checkin")
    doc.employee       = employee
    doc.shift_settings = shift_settings
    doc.shift_date     = shift_date
    doc.checkin_time   = now_datetime()
    doc.checkin_location = location or _get_ip()
    doc.marked_by      = frappe.session.user
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"name": doc.name, "checkin_time": str(doc.checkin_time), "shift_date": str(shift_date)}


# ─────────────────────────────────────────────────────────────────────────────
# Check-Out
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def agent_checkout(employee: str, shift_settings: str = None, location: str = None):
    """
    Record a check-out for an agent's current open checkin.
    Triggers attendance computation and marks Agent Attendance.
    """
    if not shift_settings:
        shift = get_active_shift()
        shift_settings = shift.name

    shift_date = _resolve_shift_date(frappe.get_doc("Shift Settings", shift_settings))

    checkin = frappe.db.get_value(
        "Agent Checkin",
        {"employee": employee, "shift_date": shift_date, "checkout_time": ("is", "not set")},
        ["name", "checkin_time"],
        as_dict=True,
    )
    if not checkin:
        frappe.throw(
            f"No open check-in found for {employee} on shift date {shift_date}.",
            title="Not Checked In",
        )

    doc = frappe.get_doc("Agent Checkin", checkin.name)
    doc.checkout_time     = now_datetime()
    doc.checkout_location = location or _get_ip()
    doc.save(ignore_permissions=True)

    # Submit to trigger _mark_attendance via on_submit
    doc.submit()
    frappe.db.commit()

    return {
        "name": doc.name,
        "status": doc.status,
        "hours_worked": doc.hours_worked,
        "late_minutes": doc.late_minutes,
        "overtime_hours": doc.overtime_hours,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Current Status
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_checkin_status(employee: str, shift_settings: str = None):
    """
    Returns whether the agent is currently checked in and the shift details.
    """
    if not shift_settings:
        try:
            shift = get_active_shift()
            shift_settings = shift.name
        except Exception:
            return {"checked_in": False, "shift_settings": None}

    shift_date = _resolve_shift_date(frappe.get_doc("Shift Settings", shift_settings))

    record = frappe.db.get_value(
        "Agent Checkin",
        {"employee": employee, "shift_date": shift_date},
        ["name", "checkin_time", "checkout_time", "status", "hours_worked"],
        as_dict=True,
    )

    if not record:
        return {"checked_in": False, "shift_date": str(shift_date), "shift_settings": shift_settings}

    return {
        "checked_in": not bool(record.checkout_time),
        "completed": bool(record.checkout_time),
        "name": record.name,
        "checkin_time": str(record.checkin_time or ""),
        "checkout_time": str(record.checkout_time or ""),
        "status": record.status or "",
        "hours_worked": record.hours_worked or 0,
        "shift_date": str(shift_date),
        "shift_settings": shift_settings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Attendance Summary (for HR view)
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_attendance_summary(from_date: str = None, to_date: str = None, employee: str = None):
    """Return Agent Attendance records for the date range."""
    if not from_date:
        from_date = today()
    if not to_date:
        to_date = today()

    filters = {
        "attendance_date": ("between", [from_date, to_date]),
    }
    if employee:
        filters["employee"] = employee

    rows = frappe.get_all(
        "Agent Attendance",
        filters=filters,
        fields=[
            "name", "employee", "employee_name", "attendance_date",
            "status", "hours_worked", "overtime_hours",
            "late_minutes", "late_entry", "early_exit",
            "shift_settings", "checkin_record",
        ],
        order_by="attendance_date desc, employee asc",
    )

    # Aggregate per employee
    summary = {}
    for r in rows:
        emp = r.employee
        if emp not in summary:
            summary[emp] = {
                "employee": emp,
                "employee_name": r.employee_name,
                "present": 0, "late": 0, "half_day": 0,
                "absent": 0, "overtime_days": 0,
                "total_hours": 0.0, "total_overtime": 0.0,
                "days": [],
            }
        s = summary[emp]
        status = (r.status or "").lower()
        if status == "present":    s["present"]       += 1
        elif status == "late":     s["late"]           += 1
        elif status == "half day": s["half_day"]       += 1
        elif status == "absent":   s["absent"]         += 1
        elif status == "overtime": s["overtime_days"]  += 1
        s["total_hours"]    += float(r.hours_worked or 0)
        s["total_overtime"] += float(r.overtime_hours or 0)
        s["days"].append(r)

    return {
        "records": rows,
        "summary": list(summary.values()),
        "from_date": from_date,
        "to_date": to_date,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Auto-mark absent (call from scheduler / cron)
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def auto_mark_absent(shift_date: str = None):
    """
    Mark all agents who have not checked in for the given shift date as Absent.
    Should be called after shift end time (e.g. 3:30 AM for night shift).
    """
    if not shift_date:
        shift_date = str(_yesterday())

    shift = get_active_shift()

    all_agents = frappe.get_all("Sales Agent", fields=["name"])

    marked = []
    for agent in all_agents:
        emp = agent.name
        has_record = frappe.db.exists(
            "Agent Attendance", {"employee": emp, "attendance_date": shift_date}
        )
        if not has_record:
            att = frappe.new_doc("Agent Attendance")
            att.employee        = emp
            att.attendance_date = shift_date
            att.shift_settings  = shift.name
            att.status          = "Absent"
            att.hours_worked    = 0
            att.remarks         = "Auto-marked absent — no check-in recorded"
            att.insert(ignore_permissions=True)
            marked.append(emp)

    frappe.db.commit()
    return {"marked_absent": marked, "count": len(marked), "shift_date": shift_date}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_shift_date(shift) -> str:
    """
    For a night shift (e.g. 6PM-3AM), the 'shift date' is the date when the
    shift STARTED (even if the agent is checking in past midnight).

    Logic: if current time is before shift_end_time (i.e. we're in the early
    hours of the next day), use yesterday as the shift date.
    """
    from cclms.call_centre_lead_management_system.doctype.shift_settings.shift_settings import _to_time
    now = datetime.now()
    if shift.crosses_midnight:
        end_time = _to_time(shift.shift_end_time)
        # If now is before end_time (e.g. 01:30 AM < 03:00 AM), shift started yesterday
        if now.time() < end_time:
            return str((now - timedelta(days=1)).date())
    return str(now.date())


def _get_ip() -> str:
    try:
        return frappe.local.request.environ.get("REMOTE_ADDR", "")
    except Exception:
        return ""


def _yesterday():
    return datetime.now().date() - timedelta(days=1)
