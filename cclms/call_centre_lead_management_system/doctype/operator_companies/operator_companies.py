# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OperatorCompanies(Document):
	pass


@frappe.whitelist(allow_guest=True)
def get_operator_companies(limit=100):
    limit = int(limit or 100)

    # Return only safe public fields
    rows = frappe.get_all(
        "Operator Companies",
        filters={"disabled": 0} if frappe.db.has_column("Operator Companies", "disabled") else {},
        fields=["name"],
        limit_page_length=limit,
        ignore_permissions=True,  # because Guest has no doctype perms
    )

    return rows
