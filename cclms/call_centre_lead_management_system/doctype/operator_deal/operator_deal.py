import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, now_datetime


STATUS_DATE_FIELD = {
    "Submitted": "submitted_date",
    "Approved": "approved_date",
    "Rejected": "rejected_date",
    "Needs Reanalysis": "needs_reanalysis_date",
    "Agreement Sent": "agreement_sent_date",
    "Signed": "signed_date",
    "Converted": "converted_date",
    "Install Scheduled": "install_scheduled_date",
    "Installed": "installed_date",
    "Cancelled": "cancelled_date",
    "Disputed": "disputed_date",
}

GLOBAL_LOCK_STATES = ("Signed", "Installed")
GLOBAL_REJECT_STATES = ("Rejected",)
SAME_OPERATOR_ACTIVE_EXCLUSIONS = ("Cancelled", "Disputed")
DEFAULT_CUTOFF = "2025-08-01"


def _safe_single_value(fieldname, default=None):
    if not frappe.db.exists("DocType", "Operator Deal Settings"):
        return default
    value = frappe.db.get_single_value("Operator Deal Settings", fieldname)
    return default if value in (None, "") else value


def _get_cutoff_datetime():
    return get_datetime(_safe_single_value("cutoff_date", DEFAULT_CUTOFF))


def _skip_strict_validation(doc):
    return bool(
        getattr(doc.flags, "in_backfill", False)
        or getattr(doc.flags, "skip_strict_duplicate_validation", False)
        or getattr(frappe.flags, "maintenance_mode", False)
    )


def _director_roles():
    raw = _safe_single_value("director_roles", "System Manager\nDirector") or ""
    return [role.strip() for role in raw.splitlines() if role.strip()]


class OperatorDeal(Document):
    def validate(self):
        self._ensure_submitted_date()
        if not _skip_strict_validation(self):
            self._stamp_current_status_date()
        self._compute_margin_fields()

        if not _skip_strict_validation(self):
            self._strict_duplicate_validation()

    def _ensure_submitted_date(self):
        if not self.submitted_date:
            if _skip_strict_validation(self) and self.creation:
                self.submitted_date = get_datetime(self.creation)
            elif not _skip_strict_validation(self):
                self.submitted_date = now_datetime()

    def _stamp_current_status_date(self):
        fieldname = STATUS_DATE_FIELD.get(self.status)
        if fieldname and not self.get(fieldname):
            self.set(fieldname, now_datetime())

    def _compute_margin_fields(self):
        budget = flt(self.budget_rent)
        agreed = flt(self.agreed_rent)
        self.margin_rent = budget - agreed if self.budget_rent is not None and self.agreed_rent is not None else 0

        recurring_operator = (_safe_single_value("recurring_margin_operator") or "").strip()
        install_threshold = int(_safe_single_value("recurring_install_threshold", 300) or 300)
        install_count = 0

        if recurring_operator and self.operator_company == recurring_operator:
            install_count = frappe.db.count(
                "Operator Deal",
                filters={"operator_company": self.operator_company, "status": "Installed"},
            )

        self.margin_eligible = int(
            self.status == "Installed"
            and bool(recurring_operator)
            and self.operator_company == recurring_operator
            and install_count >= install_threshold
            and self.margin_rent > 0
        )

    def _strict_duplicate_validation(self):
        if not self.location or not self.operator_company:
            return

        creation_dt = get_datetime(self.creation) if self.creation else now_datetime()
        if creation_dt < _get_cutoff_datetime():
            return

        if frappe.db.exists(
            "Operator Deal",
            {
                "location": self.location,
                "name": ["!=", self.name or ""],
                "status": ["in", list(GLOBAL_LOCK_STATES)],
            },
        ):
            frappe.throw("Duplicate blocked: this location is already Signed/Installed with an operator.")

        if frappe.db.exists(
            "Operator Deal",
            {
                "location": self.location,
                "name": ["!=", self.name or ""],
                "status": ["in", list(GLOBAL_REJECT_STATES)],
            },
        ):
            frappe.throw("Duplicate blocked: this location was rejected by an operator.")

        if frappe.db.exists(
            "Operator Deal",
            {
                "location": self.location,
                "operator_company": self.operator_company,
                "name": ["!=", self.name or ""],
                "status": ["not in", list(SAME_OPERATOR_ACTIVE_EXCLUSIONS)],
            },
        ):
            frappe.throw("Duplicate blocked: use the existing deal for this operator/location instead of creating a new one.")
