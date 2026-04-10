import frappe
from frappe.model.document import Document
from datetime import datetime, time, timedelta


class ShiftSettings(Document):

    def validate(self):
        self._validate_times()
        self._compute_crosses_midnight()

    def _validate_times(self):
        if not self.shift_start_time or not self.shift_end_time:
            frappe.throw("Shift Start Time and End Time are required.")

    def _compute_crosses_midnight(self):
        """Auto-detect crosses_midnight: end < start means it wraps into next day."""
        start = _to_time(self.shift_start_time)
        end   = _to_time(self.shift_end_time)
        if end <= start:
            self.crosses_midnight = 1
        else:
            self.crosses_midnight = 0

    def get_shift_duration_hours(self) -> float:
        """Return numeric shift duration in hours, accounting for midnight crossing."""
        start = _to_time(self.shift_start_time)
        end   = _to_time(self.shift_end_time)
        dt_start = datetime.combine(datetime.today(), start)
        if self.crosses_midnight:
            dt_end = datetime.combine(datetime.today() + timedelta(days=1), end)
        else:
            dt_end = datetime.combine(datetime.today(), end)
        return (dt_end - dt_start).total_seconds() / 3600


def _to_time(val) -> time:
    """Convert timedelta or string 'HH:MM:SS' to datetime.time."""
    if isinstance(val, timedelta):
        total = int(val.total_seconds())
        h, remainder = divmod(total, 3600)
        m, s = divmod(remainder, 60)
        return time(h % 24, m, s)
    if isinstance(val, str):
        parts = val.split(":")
        return time(int(parts[0]) % 24, int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    return val


def get_active_shift() -> "ShiftSettings":
    """Return the default shift settings document."""
    name = frappe.db.get_value("Shift Settings", {"default_for_all_agents": 1}, "name")
    if not name:
        name = frappe.db.get_single_value("Shift Settings", "name") or frappe.db.get_value(
            "Shift Settings", {}, "name"
        )
    if not name:
        frappe.throw("No Shift Settings configured. Please create a Shift Settings record first.")
    return frappe.get_doc("Shift Settings", name)
