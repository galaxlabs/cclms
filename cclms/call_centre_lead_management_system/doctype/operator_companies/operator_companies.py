# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


# Our own business domains (NOT Frappe's "Domain" which controls Desk modules).
# Add/remove entries here and in Follow-up Settings to extend.
BUSINESS_DOMAINS = ["BTM", "ATM", "Internet", "Insurance"]


class OperatorCompanies(Document):
    def validate(self):
        # Normalize operator name
        if self.operator_name:
            self.operator_name = (self.operator_name or "").strip()
        # Domain is required; must be from the predefined list
        if self.domain:
            if self.domain not in BUSINESS_DOMAINS:
                frappe.throw(f"Domain must be one of: {', '.join(BUSINESS_DOMAINS)}")
        # Permitted states: state code required per row
        for row in self.state_name:
            if not row.state_code:
                frappe.throw("Each Permitted State row requires a State Code")


@frappe.whitelist(allow_guest=True)
def get_operator_companies(limit=100, domain=None):
    """Return operator companies, optionally filtered by business domain."""
    limit = int(limit or 100)
    filters = {}
    if domain:
        filters["domain"] = domain
    rows = frappe.get_all(
        "Operator Companies",
        filters=filters,
        fields=["name", "domain"],
        limit_page_length=limit,
        ignore_permissions=True,
    )
    return rows


@frappe.whitelist(allow_guest=True)
def get_domains():
    return {"domains": BUSINESS_DOMAINS}
