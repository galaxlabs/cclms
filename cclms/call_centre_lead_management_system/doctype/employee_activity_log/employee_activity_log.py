# Copyright (c) 2026, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds


def _resolve_device_links(device_id=None):
    if not device_id:
        return (None, None)

    device_profile = None
    tracker_device = None
    if frappe.db.exists("DocType", "Device Profile"):
        device_profile = frappe.db.get_value("Device Profile", {"device_id": device_id}, "name")
    if frappe.db.exists("DocType", "Tracker Device"):
        tracker_device = frappe.db.get_value("Tracker Device", {"device_id": device_id}, "name")
    return (device_profile, tracker_device)


class EmployeeActivityLog(Document):
    def before_insert(self):
        if not self.login_time:
            self.login_time = now_datetime()
        self.last_heartbeat = self.last_heartbeat or now_datetime()
        self.sync_device_links()
        self.mark_attendance()

    def validate(self):
        self.sync_device_links()
        self.calculate_metrics()

    def sync_device_links(self):
        if not self.device_id:
            return

        device_profile, tracker_device = _resolve_device_links(self.device_id)
        if device_profile:
            self.device_profile = device_profile
        if tracker_device:
            self.tracker_device = tracker_device

    def mark_attendance(self):
        if not self.employee:
            return
        if not frappe.db.exists("DocType", "Employee Checkin"):
            return

        existing = frappe.db.exists(
            "Employee Checkin",
            {
                "employee": self.employee,
                "log_type": "IN",
                "time": [">=", str(self.date)],
            },
        )
        if existing:
            return

        frappe.get_doc(
            {
                "doctype": "Employee Checkin",
                "employee": self.employee,
                "time": self.login_time or now_datetime(),
                "log_type": "IN",
                "device_id": self.device_id or self.machine_name or self.name,
            }
        ).insert(ignore_permissions=True)

    def calculate_metrics(self):
        total_calls = 0
        total_call_seconds = 0
        total_active_minutes = 0.0
        total_idle_minutes = 0.0
        unauthorized_site_hits = 0

        for row in self.activity_logs or []:
            minutes = float(row.event_minutes or 0)
            if row.event_type == "Idle":
                total_idle_minutes += minutes
            else:
                total_active_minutes += minutes

            if int(row.is_authorized or 0) == 0 and row.event_type == "Website Visit":
                unauthorized_site_hits += 1

            if row.event_type == "Call" and row.call_start and row.call_end:
                total_calls += 1
                diff = max(0, int(time_diff_in_seconds(row.call_end, row.call_start)))
                row.duration = diff
                total_call_seconds += diff

        if self.login_time and self.logout_time:
            shift_seconds = max(0, int(time_diff_in_seconds(self.logout_time, self.login_time)))
            if total_active_minutes <= 0 and total_idle_minutes <= 0 and shift_seconds:
                total_active_minutes = round(shift_seconds / 60.0, 2)

        self.total_calls_today = total_calls
        self.total_talk_time = total_call_seconds
        self.total_active_minutes = round(total_active_minutes, 2)
        self.total_idle_minutes = round(total_idle_minutes, 2)
        self.unauthorized_site_hits = unauthorized_site_hits
        self.log_time = self.last_heartbeat or self.log_time or now_datetime()

        if self.logout_time:
            self.status = "Logged Out"
        elif total_idle_minutes > total_active_minutes and total_idle_minutes > 10:
            self.status = "Idle"
        else:
            self.status = self.status or "Active"


def close_stale_logs(idle_minutes=15):
    cutoff = now_datetime()
    rows = frappe.get_all(
        "Employee Activity Log",
        filters={"status": ["in", ["Active", "Idle"]]},
        fields=["name", "last_heartbeat"],
        limit_page_length=500,
    )

    updated = 0
    for row in rows:
        heartbeat = get_datetime(row.last_heartbeat) if row.last_heartbeat else None
        if not heartbeat:
            continue
        if time_diff_in_seconds(cutoff, heartbeat) < int(idle_minutes) * 60:
            continue
        frappe.db.set_value(
            "Employee Activity Log",
            row.name,
            {
                "status": "Closed",
                "logout_time": heartbeat,
            },
            update_modified=False,
        )
        updated += 1

    if updated:
        frappe.db.commit()
    return {"updated": updated}


def backfill_device_links(limit=0):
    rows = frappe.get_all(
        "Employee Activity Log",
        filters={"device_id": ["!=", ""]},
        fields=["name", "device_id", "device_profile", "tracker_device"],
        limit_page_length=int(limit) if limit else 0,
        order_by="modified desc",
    )

    updated = 0
    for row in rows:
        device_profile, tracker_device = _resolve_device_links(row.device_id)
        values = {}
        if device_profile and row.device_profile != device_profile:
            values["device_profile"] = device_profile
        if tracker_device and row.tracker_device != tracker_device:
            values["tracker_device"] = tracker_device
        if not values:
            continue
        frappe.db.set_value("Employee Activity Log", row.name, values, update_modified=False)
        updated += 1

    if updated:
        frappe.db.commit()
    return {"updated": updated}
