# Copyright (c) 2025, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


def _clip(value, length=140):
    if value in (None, ""):
        return value
    return str(value)[:length]


class CompetitorKiosk(Document):
    def validate(self):
        # Guard long Google Maps values before Frappe's field-length validation runs.
        for fieldname in ("source", "place_id", "display_name", "address", "city", "state_code", "brand", "provider"):
            if hasattr(self, fieldname):
                setattr(self, fieldname, _clip(getattr(self, fieldname)))
