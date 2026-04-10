# Copyright (c) 2026, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AgentStageLedger(Document):
    """
    Immutable ledger of every ATM Lead workflow-state transition.

    Rules enforced:
    - Once inserted, NO field can be modified (not even by System Manager via UI).
    - Deletion is blocked for everyone except Administrator (for emergency cleanup only).
    - Records are inserted automatically by ATMLeads.log_workflow_change()
      via insert(ignore_permissions=True); never created manually.
    """

    def before_save(self):
        """Block any modification to existing ledger entries."""
        if not self.is_new():
            frappe.throw(
                _(
                    "Agent Stage Ledger entries are immutable. "
                    "This record cannot be modified after creation."
                ),
                title=_("Immutable Record"),
                exc=frappe.PermissionError,
            )

    def on_trash(self):
        """Only Administrator can delete a ledger entry (emergency use only)."""
        if frappe.session.user != "Administrator":
            frappe.throw(
                _(
                    "Agent Stage Ledger entries cannot be deleted. "
                    "Contact Administrator for emergency removal."
                ),
                title=_("Deletion Not Allowed"),
                exc=frappe.PermissionError,
            )
