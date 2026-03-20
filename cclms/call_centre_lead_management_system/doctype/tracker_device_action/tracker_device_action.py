import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class TrackerDeviceAction(Document):
    def validate(self):
        if not self.created_at:
            self.created_at = now_datetime()
        if self.device_id and not self.tracker_device:
            self.tracker_device = frappe.db.get_value("Tracker Device", {"device_id": self.device_id}, "name")
