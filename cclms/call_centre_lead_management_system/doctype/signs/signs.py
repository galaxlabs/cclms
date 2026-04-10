# Copyright (c) 2025, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime


# Workflow states on ATM Leads that permit a Signs record to be created/linked
_VALID_LEAD_STATES = frozenset(["Signed", "Pending Sign"])

# States where the Signs record becomes locked from further edits
_LOCKED_LEAD_STATES = frozenset(["Installed", "installed/Removed", "Converted"])

# Flag set on the document when auto-created by the ATM Leads system
_AUTO_CREATE_FLAG = "_auto_created_by_system"


class Signs(Document):
    """
    Signs DocType controller.

    Responsibilities:
    - Validate that the linked ATM Lead is in an acceptable state (Signed / Pending Sign).
    - Lock the Signs record from editing once the linked lead reaches Installed or beyond.
    - Write a transition event to Agent Stage Ledger on creation.
    - Closing Agent field is left blank for the manager to fill in (commission/reward assignment).

    Auto-creation:
    - ATMLeads._create_signs_record() inserts this doc automatically when a lead
      transitions to "Signed" state, setting _auto_created_by_system=True to bypass
      the state validation (since the transition and creation happen in the same save cycle).
    """

    def before_insert(self):
        # Skip state validation for system auto-creation — the state IS being set to Signed
        # in the same transaction, so the DB value may not yet reflect it.
        if not getattr(self, _AUTO_CREATE_FLAG, False):
            self._validate_lead_state()
        self._write_stage_ledger_event("Signs Created")

    def validate(self):
        if not getattr(self, _AUTO_CREATE_FLAG, False):
            self._validate_lead_state()
        self._check_lock()

    def on_update(self):
        """When closing_agent is filled in, write a ledger event."""
        if self.closing_agent:
            old = self.get_doc_before_save() or frappe._dict()
            old_agent = getattr(old, "closing_agent", None)
            if old_agent != self.closing_agent:
                self._write_stage_ledger_event(
                    f"Closing Agent Assigned: {self.closing_agent}"
                )

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _validate_lead_state(self):
        """Raise if the linked ATM Lead is not in a sign-eligible state."""
        if not self.atm_leads:
            return

        lead_state = frappe.db.get_value("ATM Leads", self.atm_leads, "workflow_state")
        if not lead_state:
            frappe.throw(
                _("The selected ATM Lead ({0}) has no workflow state.").format(self.atm_leads),
                title=_("Invalid Lead State"),
            )

        if lead_state not in _VALID_LEAD_STATES:
            frappe.throw(
                _(
                    "Signs can only be created for ATM Leads in "
                    "<b>Signed</b> or <b>Pending Sign</b> state.<br>"
                    "Lead <b>{0}</b> is currently in state: <b>{1}</b>."
                ).format(
                    frappe.utils.get_link_to_form("ATM Leads", self.atm_leads),
                    lead_state,
                ),
                title=_("Lead Not Signed"),
            )

    def _check_lock(self):
        """
        Prevent editing Signs records once the linked lead has progressed
        to Installed, Converted, or Removed (deal is fully closed).
        Administrator may still edit for corrections.
        """
        if frappe.session.user == "Administrator":
            return
        if not self.atm_leads or self.is_new():
            return

        lead_state = frappe.db.get_value("ATM Leads", self.atm_leads, "workflow_state")
        if lead_state in _LOCKED_LEAD_STATES:
            frappe.throw(
                _(
                    "This Signs record is locked because the ATM Lead is in "
                    "<b>{0}</b> state. Contact Administrator to make changes."
                ).format(lead_state),
                title=_("Record Locked"),
                exc=frappe.PermissionError,
            )

    def _write_stage_ledger_event(self, event_label: str):
        """Record a sign event in Agent Stage Ledger (best-effort, never blocks)."""
        try:
            if not frappe.db.exists("DocType", "Agent Stage Ledger"):
                return
            if not self.atm_leads:
                return

            lead = frappe.get_doc("ATM Leads", self.atm_leads)
            frappe.get_doc({
                "doctype": "Agent Stage Ledger",
                "lead": self.atm_leads,
                "employee": lead.executive_name or "",
                "company": lead.company or "",
                "branch": lead.branch or "",
                "state_code": lead.state_code or "",
                "from_state": lead.workflow_state or "Signed",
                "to_state": f"[Sign Event] {event_label}",
                "stage_datetime": now_datetime(),
                "stage_date": nowdate(),
                "days_in_prev_state": 0,
                "changed_by": frappe.session.user or "Administrator",
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Signs: Agent Stage Ledger event failed")

