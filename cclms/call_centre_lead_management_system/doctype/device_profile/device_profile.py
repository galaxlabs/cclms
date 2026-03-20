import frappe
from frappe.model.document import Document


def _resolve_employee(user=None):
    if not user:
        return None
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _resolve_sales_agent(user=None, employee=None):
    if not frappe.db.exists("DocType", "Sales Agent"):
        return None

    meta = frappe.get_meta("Sales Agent")
    fieldnames = {field.fieldname for field in meta.fields}
    if user and "user" in fieldnames:
        value = frappe.db.get_value("Sales Agent", {"user": user}, "name")
        if value:
            return value
    if user and "email" in fieldnames:
        value = frappe.db.get_value("Sales Agent", {"email": user}, "name")
        if value:
            return value
    if employee and "employee" in fieldnames:
        return frappe.db.get_value("Sales Agent", {"employee": employee}, "name")
    return None


class DeviceProfile(Document):
    def validate(self):
        if self.tracked_user and not self.employee:
            self.employee = _resolve_employee(self.tracked_user)
        if self.tracked_user and not self.sales_agent:
            self.sales_agent = _resolve_sales_agent(self.tracked_user, self.employee)
        self.sync_tracker_device()

    def sync_tracker_device(self):
        active = 0 if (self.status or "").lower() == "blocked" else 1
        tracker_values = {
            "tracked_user": self.tracked_user,
            "employee": self.employee,
            "allowed_service_user": self.allowed_service_user,
            "machine_name": self.machine_name,
            "ip_address": self.ip_address,
            "active": active,
            "notes": self.notes,
        }

        tracker_name = frappe.db.get_value("Tracker Device", {"device_id": self.device_id}, "name")
        if tracker_name:
            frappe.db.set_value("Tracker Device", tracker_name, tracker_values, update_modified=False)
            self.tracker_device = tracker_name
            return

        tracker = frappe.get_doc(
            {
                "doctype": "Tracker Device",
                "device_id": self.device_id,
                **tracker_values,
            }
        )
        tracker.insert(ignore_permissions=True)
        self.tracker_device = tracker.name
