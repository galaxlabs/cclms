# Copyright (c) 2026, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_seconds, get_datetime, now_datetime

class EmployeeActivityLog(Document):
    def before_insert(self):
        # Automatically mark Attendance in HRMS when the first log of the day is created
        self.mark_attendance()

    def validate(self):
        self.calculate_call_metrics()

    def mark_attendance(self):
        # Prevent duplicate check-ins for the same session
        if not frappe.db.exists("Employee Checkin", {"employee": self.employee, "time": [">=", self.date]}):
            checkin = frappe.get_doc({
                "doctype": "Employee Checkin",
                "employee": self.employee,
                "time": now_datetime(),
                "log_type": "IN",
                "device_id": self.name 
            })
            checkin.insert(ignore_permissions=True)

    def calculate_call_metrics(self):
        total_calls = 0
        total_seconds = 0
        for row in self.activity_logs:
            if row.event_type == "Call" and row.call_start and row.call_end:
                total_calls += 1
                diff = time_diff_in_seconds(row.call_end, row.call_start)
                row.duration = diff
                total_seconds += diff
        
        self.total_calls_today = total_calls
        self.total_talk_time = total_seconds

@frappe.whitelist()
def upload_activity_snap(employee, screenshot_base64, active_app):
    # 1. Get today's parent session
    session_name = get_or_create_daily_session(employee)
    
    # 2. Save the image file
    file_url = save_base64_image(screenshot_base64, employee)
    
    # 3. Add to the child table 'activity_logs'
    doc = frappe.get_doc("Employee Activity Log", session_name)
    doc.append("activity_logs", {
        "event_time": frappe.utils.now_datetime(),
        "event_type": "Screen Snap",
        "screenshot": file_url,
        "active_app": active_app,
        "summary": f"Automatic snap from {active_app}"
    })
    
    doc.save(ignore_permissions=True)
    frappe.db.commit() # Important for background/API triggers
    
    return {"status": "success", "file_url": file_url}