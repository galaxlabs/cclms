import frappe
from frappe.model.document import Document


class AgentAttendance(Document):

    def validate(self):
        # Prevent duplicate attendance for same employee + date
        existing = frappe.db.get_value(
            "Agent Attendance",
            {
                "employee": self.employee,
                "attendance_date": self.attendance_date,
                "name": ("!=", self.name or ""),
            },
            "name",
        )
        if existing:
            frappe.throw(
                f"Attendance already marked for {self.employee} on {self.attendance_date} "
                f"(record: {existing})"
            )
