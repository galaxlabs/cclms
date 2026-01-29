# Copyright (c) 2026, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

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
}

class OperatorDeal(Document):
    def validate(self):
        self._stamp_status_date()

    def on_update(self):
        # optional: enforce your global lock rules here too
        pass

    def _stamp_status_date(self):
        fieldname = STATUS_DATE_FIELD.get(self.status)
        if fieldname and not self.get(fieldname):
            self.set(fieldname, now_datetime())
