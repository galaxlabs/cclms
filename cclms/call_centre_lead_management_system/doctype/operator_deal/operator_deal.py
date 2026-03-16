# Copyright (c) 2026, Galaxy and contributors
# For license information, please see license.txt

# ~/dg-b/apps/cclms/cclms/doctype/operator_deal/operator_deal.py

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime

CUTOFF = get_datetime("2025-08-01")

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

LOCK_SIGNED_STATES = ("Signed", "Installed")
LOCK_REJECTED_STATES = ("Rejected",)


class OperatorDeal(Document):
    def validate(self):
        self._stamp_status_date()
        self._compute_margin_fields()

        if not getattr(self.flags, "in_backfill", False):
            self._strict_duplicate_validation()

    def before_insert(self):
        # If you want a default submitted_date on insert (optional)
        if not self.submitted_date:
            self.submitted_date = now_datetime()

    # -------------------------
    # 1) Date stamping by status
    # -------------------------
    def _stamp_status_date(self):
        fieldname = STATUS_DATE_FIELD.get(self.status)
        if fieldname and not self.get(fieldname):
            self.set(fieldname, now_datetime())

    # -------------------------
    # 2) Margin compute (Director-only fields)
    # -------------------------
    def _compute_margin_fields(self):
        # margin_rent = budget_rent - agreed_rent (if both set)
        budget = self.budget_rent
        agreed = self.agreed_rent

        if budget is None or agreed is None:
            self.margin_rent = 0
        else:
            try:
                self.margin_rent = float(budget) - float(agreed)
            except Exception:
                self.margin_rent = 0

        # margin_eligible (simple v1 rule)
        # - only makes sense if installed and margin > 0
        self.margin_eligible = 1 if (self.status == "Installed" and (self.margin_rent or 0) > 0) else 0

    # -------------------------
    # 3) Strict duplication rules (new-era only)
    # -------------------------
    def _strict_duplicate_validation(self):
        # Only enforce strict duplication for records on/after cutoff
        created = get_datetime(self.creation) if self.creation else None
        if created and created < CUTOFF:
            return

        if not self.location or not self.operator_company:
            return

        # 1) If ANY signed/installed exists for this location -> block (new-era only)
        if frappe.db.sql(
            """
            SELECT name
            FROM `tabOperator Deal`
            WHERE location=%s
              AND name!=%s
              AND status IN ('Signed','Installed')
              AND creation >= %s
            LIMIT 1
            """,
            (self.location, self.name, CUTOFF),
        ):
            frappe.throw("Duplicate blocked: this location is already Signed/Installed.")

        # 2) If ANY rejected exists for this location -> block global (new-era only)
        if frappe.db.sql(
            """
            SELECT name
            FROM `tabOperator Deal`
            WHERE location=%s
              AND name!=%s
              AND status IN ('Rejected')
              AND creation >= %s
            LIMIT 1
            """,
            (self.location, self.name, CUTOFF),
        ):
            frappe.throw("Duplicate blocked: this location was rejected by an operator.")

        # 3) Same operator duplication not allowed (except Cancelled/Disputed) (new-era only)
        if frappe.db.sql(
            """
            SELECT name
            FROM `tabOperator Deal`
            WHERE location=%s
              AND operator_company=%s
              AND name!=%s
              AND status NOT IN ('Cancelled','Disputed')
              AND creation >= %s
            LIMIT 1
            """,
            (self.location, self.operator_company, self.name, CUTOFF),
        ):
            frappe.throw("Duplicate blocked: deal already exists for this operator.")
