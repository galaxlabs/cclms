import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, getdate, get_datetime
from datetime import datetime, timedelta, time as dtime

from cclms.call_centre_lead_management_system.doctype.shift_settings.shift_settings import (
    get_active_shift,
    _to_time,
)


class AgentCheckin(Document):

    # ─── Lifecycle ────────────────────────────────────────────────────────

    def before_save(self):
        if self.checkin_time and self.checkout_time:
            self._compute_attendance()

    def on_submit(self):
        self._mark_attendance()

    # ─── Core computation ─────────────────────────────────────────────────

    def _compute_attendance(self):
        shift = frappe.get_doc("Shift Settings", self.shift_settings)

        ci = get_datetime(self.checkin_time)
        co = get_datetime(self.checkout_time)

        if co <= ci:
            frappe.throw("Check-Out time must be after Check-In time.")

        # Raw hours worked (minus break)
        raw_hours = (co - ci).total_seconds() / 3600
        break_hours = (shift.break_duration_minutes or 0) / 60
        if shift.break_deductible:
            hours_worked = max(0.0, raw_hours - break_hours)
        else:
            hours_worked = raw_hours

        self.hours_worked   = round(hours_worked, 2)
        self.late_minutes   = self._calc_late_minutes(shift, ci)
        self.overtime_hours = self._calc_overtime(shift, hours_worked)
        self.is_half_day    = 1 if (
            (shift.absent_threshold_hours or 2) <= hours_worked < (shift.half_day_threshold_hours or 4.5)
        ) else 0
        self.status         = self._derive_status(shift, hours_worked)

    def _calc_late_minutes(self, shift, checkin_dt: datetime) -> int:
        """Minutes the agent was late beyond grace period. 0 if on time."""
        shift_start = _to_time(shift.shift_start_time)
        shift_date  = checkin_dt.date()

        # Night shift: shift_start is e.g. 18:00, date is the *start* calendar day
        expected_start = datetime.combine(shift_date, shift_start)

        grace = timedelta(minutes=int(shift.grace_period_minutes or 15))
        allowed_start = expected_start + grace

        if checkin_dt <= allowed_start:
            return 0
        delta = checkin_dt - allowed_start
        return int(delta.total_seconds() / 60)

    def _calc_overtime(self, shift, hours_worked: float) -> float:
        if not shift.allow_overtime:
            return 0.0
        expected = float(shift.working_hours or 9)
        ot = max(0.0, hours_worked - expected)
        max_ot = float(shift.max_overtime_hours or 3)
        return round(min(ot, max_ot), 2)

    def _derive_status(self, shift, hours_worked: float) -> str:
        absent_threshold = float(shift.absent_threshold_hours or 2)
        half_day_thresh  = float(shift.half_day_threshold_hours or 4.5)
        expected_hours   = float(shift.working_hours or 9)

        if hours_worked < absent_threshold:
            return "Absent"
        if hours_worked < half_day_thresh:
            return "Half Day"
        if self.late_minutes and int(self.late_minutes) > int(shift.late_mark_after_minutes or 30):
            return "Late"
        if hours_worked > expected_hours and shift.allow_overtime:
            return "Overtime"
        return "Present"

    # ─── Mark Attendance (Agent Attendance DocType) ───────────────────────

    def _mark_attendance(self):
        """Create or update Agent Attendance record from this checkin."""
        if frappe.db.exists(
            "Agent Attendance",
            {"employee": self.employee, "attendance_date": self.shift_date},
        ):
            att = frappe.get_doc(
                "Agent Attendance",
                {"employee": self.employee, "attendance_date": self.shift_date},
            )
        else:
            att = frappe.new_doc("Agent Attendance")
            att.employee        = self.employee
            att.attendance_date = self.shift_date
            att.shift_settings  = self.shift_settings

        att.status         = self.status or "Absent"
        att.hours_worked   = self.hours_worked or 0
        att.overtime_hours = self.overtime_hours or 0
        att.late_minutes   = self.late_minutes or 0
        att.late_entry     = 1 if (self.late_minutes and int(self.late_minutes) > 0) else 0
        att.early_exit     = 1 if (
            self.checkout_time and self.hours_worked and
            float(self.hours_worked) < float(
                frappe.db.get_value("Shift Settings", self.shift_settings, "working_hours") or 9
            )
        ) else 0
        att.checkin_record = self.name
        att.save(ignore_permissions=True)
