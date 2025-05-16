import frappe
import json
from frappe import _

@frappe.whitelist(allow_guest=False)
def create_batch_attendance_logs(data):
    try:

        logs = json.loads(data)
        for log in logs:
            doc = frappe.get_doc({
                "doctype": "EmployeeAttendanceLog",
                "employee_device_id": log.get("employee_device_id"),
                "employee_name": log.get("employee_name"),
                "attendance_date": log.get("attendance_date"),
                "attendance_time": log.get("attendance_time"),
                "verify_mode": log.get("verify_mode"),
                "inout_mode": log.get("inout_mode")
            })
            doc.insert(ignore_permissions=True)
        return {"status": "success", "message": f"{len(logs)} logs inserted"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Batch Log Insert Failed")
        return {"status": "error", "message": str(e)}
