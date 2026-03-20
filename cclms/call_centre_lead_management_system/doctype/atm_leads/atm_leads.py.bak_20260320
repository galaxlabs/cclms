# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, nowdate, getdate


class ATMLeads(Document):
    """
    ATM Leads DocType controller.

    Responsibilities:
    - Business validation (company, state restrictions, etc.)
    - Tracking workflow_state changes into child table `state_history`
      (DocType: "ATM Lead State History")
    - Computing `days_in_state` per transition.
    """

    # -------------------------------
    # Standard hooks
    # -------------------------------

    def validate(self):
        self.validate_lead_state()

    def before_save(self):
        # Track workflow changes into child table
        self.log_workflow_change()

    # -------------------------------
    # Business validation
    # -------------------------------

    def validate_lead_state(self):
        """Basic lead validation: company, address, permitted states, etc."""

        # Company required
        if not self.company:
            frappe.throw(
                _("Please select a company before saving the lead."),
                title=_("Company Not Selected"),
            )

        # Address required
        if not self.address:
            frappe.throw(
                _("Please enter a valid address."),
                title=_("Address Required"),
            )

        # Company must exist
        company = frappe.get_doc("Operator Companies", self.company)
        if not company:
            frappe.throw(
                _("The selected company does not exist."),
                title=_("Invalid Company"),
            )

        # State restriction based on company.permitted_states child table
        permitted_states = company.get("permitted_states")
        if permitted_states:
            if not any(state.state_code == self.state_code for state in permitted_states):
                frappe.throw(
                    _("The selected state ({0}) is not allowed for the company {1}.")
                    .format(self.state_code, self.company),
                    title=_("State Not Allowed"),
                )
        else:
            # No restrictions configured
            frappe.msgprint(
                _("No restricted states specified for this company. All states are allowed."),
                alert=True,
            )

    # -------------------------------
    # Workflow state history tracking (runtime)
    # -------------------------------

    def log_workflow_change(self):
        """
        Append a row in state_history whenever `workflow_state` changes.

        Rules:
        - We ignore doc creation as a "state change" (no None -> Draft row).
        - First meaningful transition is usually Draft -> Submitted.
        - For each transition, we update `days_in_state` for the previous state.
        - Child fieldname on ATM Leads: state_history (Table → ATM Lead State History)
        """

        old_doc = self.get_doc_before_save() or frappe._dict()

        old_state = getattr(old_doc, "workflow_state", None)
        new_state = self.workflow_state

        # If workflow_state not set or unchanged, nothing to record
        if not new_state or old_state == new_state:
            return

        # Ignore initial creation if it's just setting Draft
        if old_state is None and new_state == "Draft":
            return

        today = nowdate()
        today_date = getdate(today)

        # Do we already have history rows?
        prev_row = self.state_history[-1] if self.state_history else None
        first_change = prev_row is None

        # Determine start date for previous state's duration
        if prev_row and prev_row.change_date:
            # Previous state started at last transition
            start_date = getdate(prev_row.change_date)
        else:
            # First tracked transition: assume we were in Draft from post_date
            start_date = getdate(self.post_date) if self.post_date else today_date

        days_in_prev_state = (today_date - start_date).days

        # Update duration on previous row (for its "to_state")
        if prev_row:
            prev_row.days_in_state = days_in_prev_state

        # Determine from_state for new row
        if first_change:
            # First meaningful event: Draft -> new_state
            from_state = "Draft"
        else:
            from_state = old_state or "Draft"

        # Append new history row
        row = self.append("state_history", {})
        row.from_state = from_state
        row.to_state = new_state
        row.change_datetime = now_datetime()
        row.change_date = today
        row.changed_by = frappe.session.user or "Administrator"
        row.agent_name = self.executive_name or ""   # plain text
        row.days_in_state = 0  # will be updated on next transition

        # Optional debug log (remove if noisy)
        frappe.logger("atm_state_history").info(
            f"[ATMLeads] {self.name}: {from_state} -> {new_state}, "
            f"prev_days={days_in_prev_state}"
        )

    # -------------------------------
    # Simple backfill for a single lead (fallback)
    # -------------------------------

    def sync_state_history_once(self):
        """
        Ensure this lead has a reasonable state history when Version is not available.

        Behavior:
        - If history is empty:
            -> Create one row: Draft -> current workflow_state
               with change_date = post_date or today.
        - If history exists but last.to_state != current workflow_state:
            -> Append row: last.to_state -> current workflow_state
               and update last.days_in_state.
        - If already in sync:
            -> Do nothing.

        Returns:
            True if document was changed and should be saved, else False.
        """

        today = nowdate()
        today_date = getdate(today)

        current_state = self.workflow_state or "Draft"

        # CASE 1: No history at all
        if not self.state_history:
            # Decide the change_date: use post_date if available, else today
            if self.post_date:
                change_date = getdate(self.post_date)
            else:
                change_date = today_date

            row = self.append("state_history", {})
            row.from_state = "Draft"
            row.to_state = current_state
            row.change_datetime = now_datetime()
            row.change_date = change_date
            row.changed_by = frappe.session.user or "Administrator"
            row.agent_name = self.executive_name or ""

            # Days in Draft from post_date to change_date
            if self.post_date:
                row.days_in_state = (change_date - getdate(self.post_date)).days
            else:
                row.days_in_state = 0

            frappe.logger("atm_state_history").info(
                f"[ATMLeads.sync_state_history_once] Seeded history for {self.name}: Draft -> {current_state}"
            )

            return True  # document changed

        # CASE 2: History exists, check if last state matches current workflow_state
        last_row = self.state_history[-1]
        last_state = last_row.to_state or "Draft"

        # Already in sync
        if last_state == current_state:
            return False

        # Need to add a transition from last_state -> current_state
        if last_row.change_date:
            start_date = getdate(last_row.change_date)
        else:
            start_date = getdate(self.post_date) if self.post_date else today_date

        days_in_prev = (today_date - start_date).days
        last_row.days_in_state = days_in_prev

        new_row = self.append("state_history", {})
        new_row.from_state = last_state
        new_row.to_state = current_state
        new_row.change_datetime = now_datetime()
        new_row.change_date = today
        new_row.changed_by = frappe.session.user or "Administrator"
        new_row.agent_name = self.executive_name or ""
        new_row.days_in_state = 0

        frappe.logger("atm_state_history").info(
            f"[ATMLeads.sync_state_history_once] Appended transition for {self.name}: {last_state} -> {current_state}"
        )

        return True  # document changed

    # -------------------------------
    # Rebuild full state history from Version
    # -------------------------------

    def rebuild_state_history_from_versions(self):
        """
        Rebuild the entire state_history table for this lead,
        based on Version records where workflow_state changed.

        - Clears existing state_history.
        - Looks at all Version entries for this doc.
        - For each workflow_state change, appends a row.
        - Calculates days_in_state as days spent in from_state
          (from previous change or post_date).
        """

        # Clear any existing rows
        self.set("state_history", [])

        # Get all Version records for this lead
        versions = frappe.get_all(
            "Version",
            filters={
                "ref_doctype": "ATM Leads",
                "docname": self.name,
            },
            fields=["name", "owner", "creation", "data"],
            order_by="creation asc",
        )
        transitions = []

        for v in versions:
            if not v.get("data"):
                continue

            # data is JSON like: {"changed": [["workflow_state", "Old", "New"], ...], ...}
            try:
                data = frappe.parse_json(v["data"])
            except Exception:
                continue

            changed = data.get("changed") or []
            for change in changed:
                # change is [fieldname, old_value, new_value]
                if len(change) >= 3 and change[0] == "workflow_state":
                    old_state = change[1] or "Draft"
                    new_state = change[2] or old_state
                    transitions.append(
                        {
                            "from_state": old_state,
                            "to_state": new_state,
                            "change_datetime": v["creation"],
                            "change_date": getdate(v["creation"]),
                            "changed_by": v["owner"],
                        }
                    )

        # If no transitions found from Version, fall back to simple single-row logic
        if not transitions:
            return self.sync_state_history_once()

        # Now build rows with days_in_state
        # First state's "from_state" duration is from post_date to its change_date
        prev_change_date = None

        for idx, t in enumerate(transitions):
            cd = t["change_date"]

            if idx == 0:
                # First transition: Draft -> first_state, days in Draft
                if self.post_date:
                    start_date = getdate(self.post_date)
                else:
                    start_date = cd
            else:
                # Duration from previous change to this change
                start_date = prev_change_date or cd

            days_in = (cd - start_date).days

            row = self.append("state_history", {})
            row.from_state = t["from_state"]
            row.to_state = t["to_state"]
            row.change_datetime = t["change_datetime"]
            row.change_date = cd
            row.changed_by = t["changed_by"]
            row.agent_name = self.executive_name or ""
            row.days_in_state = days_in

            prev_change_date = cd

        frappe.logger("atm_state_history").info(
            f"[ATMLeads.rebuild_state_history_from_versions] {self.name}: "
            f"{len(transitions)} transitions rebuilt from Version"
        )

        return True


# -------------------------------
# Global backfill / scheduler entry
# -------------------------------

@frappe.whitelist()
def sync_recent_lead_state_history(from_date=None, limit=1000):
    """
    Rebuild full state history from Version for ATM Leads from a given date onwards.

    Intended usage:
    - Daily scheduler at 5am PKT, processing up to `limit` leads.
    - Only leads with post_date >= from_date are included.

    Args:
        from_date (str | None): "YYYY-MM-DD", default "2025-08-10"
        limit (int): max number of leads to process in one run (default 1000)

    Returns:
        dict: {"processed": N, "changed": M, "failed": F, "errors": [...]}
    """

    if not from_date:
        from_date = "2025-08-10"

    filters = {
        "docstatus": ["<", 2],
        "post_date": [">=", from_date],
    }

    leads = frappe.get_all(
        "ATM Leads",
        filters=filters,
        fields=["name"],
        order_by="post_date asc, name asc",
        limit=limit,
    )

    processed = 0
    changed_docs = 0
    failed = 0
    errors = []

    for l in leads:
        doc = frappe.get_doc("ATM Leads", l.name)

        try:
            # Rebuild from Version; if no Version found, it falls back to sync_state_history_once()
            if hasattr(doc, "rebuild_state_history_from_versions"):
                changed = doc.rebuild_state_history_from_versions()
            else:
                changed = False

            if changed:
                # Ignore validation/mandatory for backfill only
                doc.flags.ignore_validate = True
                doc.flags.ignore_mandatory = True
                doc.save(ignore_permissions=True)
                changed_docs += 1

        except Exception as e:
            failed += 1
            # Capture full traceback so bench execute can show it
            errors.append({
                "lead": doc.name,
                "error": str(e),
                "traceback": frappe.get_traceback()
            })
            frappe.logger("atm_state_history").error(
                f"[sync_recent_lead_state_history] Failed for {doc.name}: {e}"
            )

        processed += 1

    frappe.db.commit()

    result = {
        "from_date": from_date,
        "processed": processed,
        "changed": changed_docs,
        "failed": failed,
        "errors": errors,
    }

    frappe.logger("atm_state_history").info(
        f"[sync_recent_lead_state_history] {result}"
    )

    return result

# import frappe
# from frappe import _
# from frappe.model.document import Document
# from frappe.utils import now_datetime, nowdate, getdate


# class ATMLeads(Document):

#     def validate(self):
#         # keep your business rules
#         self.validate_lead_state()

#     def before_save(self):
#         # log workflow changes & durations
#         self.log_status_change()

#     def validate_lead_state(self):
#         # -------------------------------
#         # Basic Required Fields
#         # -------------------------------
#         if not self.company:
#             frappe.throw(_("Please select a company before saving the lead."), title=_("Company Not Selected"))

#         if not self.address:
#             frappe.throw(_("Please enter a valid address."), title=_("Address Required"))

#         # -------------------------------
#         # Validate Company Exists
#         # -------------------------------
#         company = frappe.get_doc("Operator Companies", self.company)
#         if not company:
#             frappe.throw(_("The selected company does not exist."), title=_("Invalid Company"))

#         # -------------------------------
#         # State Restriction Check
#         # -------------------------------
#         permitted_states = company.get("permitted_states")
#         if permitted_states:
#             if not any(state.state_code == self.state_code for state in permitted_states):
#                 frappe.throw(
#                     _("The selected state ({0}) is not allowed for the company {1}.")
#                     .format(self.state_code, self.company),
#                     title=_("State Not Allowed"),
#                 )
#         else:
#             frappe.msgprint(
#                 _("No restricted states specified for this company. All states are allowed."),
#                 alert=True,
#             )

#         # duplicate check intentionally disabled here
#         return

#     # -------------------------------
#     # State history + duration
#     # -------------------------------

#     def log_status_change(self):
#         """
#         Append a row in state_history whenever `status` changes.

#         Also update `days_in_state` for the *previous* state based on:
#         - previous change_date (from last history row), or
#         - post_date, if this is the first transition.
#         """

#         old = self.get_doc_before_save() or frappe._dict()
#         old_status = getattr(old, "status", None)
#         new_status = self.status

#         # No change or no new status -> nothing to log
#         if not new_status or old_status == new_status:
#             return

#         today = nowdate()

#         # Find last history row (if any)
#         prev_row = self.state_history[-1] if self.state_history else None

#         # Starting date for previous state's duration:
#         # - If we have a previous row, start from its change_date
#         # - If not, start from lead.post_date
#         if prev_row and prev_row.change_date:
#             start_date = getdate(prev_row.change_date)
#         else:
#             start_date = getdate(self.post_date) if self.post_date else getdate(today)

#         # Duration in days until today
#         days_in_prev_state = (getdate(today) - start_date).days

#         # Store duration on the previous row (duration of its "to_state")
#         if prev_row:
#             prev_row.days_in_state = days_in_prev_state

#         # Now append new history row for this transition
#         row = self.append("state_history", {})
#         row.from_state = old_status or "None"
#         row.to_state = new_status
#         row.change_datetime = now_datetime()
#         row.change_date = today
#         row.changed_by = frappe.session.user
#         row.agent = self.executive_name
#         row.post_date = self.post_date
#         # New state hasn't finished yet, so 0 for now.
#         row.days_in_state = 0
#         row.lead_name = self.name



# import frappe
# import datetime
# from frappe import _
# from frappe.utils import date_diff, nowdate
# from frappe.model.document import Document
# from datetime import timedelta
# import requests

# #from frappe.utils import today, add_days

# class ATMLeads(Document):

#     def validate(self):
#         self.validate_lead_state()

#     def validate_lead_state(self):
#         # -------------------------------
#         # Basic Required Fields
#         # -------------------------------
#         if not self.company:
#             frappe.throw(_("Please select a company before saving the lead."), title=_("Company Not Selected"))

#         if not self.address:
#             frappe.throw(_("Please enter a valid address."), title=_("Address Required"))

#         # -------------------------------
#         # Validate Company Exists
#         # -------------------------------
#         company = frappe.get_doc('Operator Companies', self.company)
#         if not company:
#             frappe.throw(_("The selected company does not exist."), title=_("Invalid Company"))

#         # -------------------------------
#         # State Restriction Check
#         # -------------------------------
#         permitted_states = company.get("permitted_states")
#         if permitted_states:
#             if not any(state.state_code == self.state_code for state in permitted_states):
#                 frappe.throw(
#                     _("The selected state ({0}) is not allowed for the company {1}.")
#                     .format(self.state_code, self.company),
#                     title=_("State Not Allowed")
#                 )
#         else:
#             frappe.msgprint(_("No restricted states specified for this company. All states are allowed."), alert=True)

#         # -------------------------------
#         # Duplicate Check (Disabled)
#         # -------------------------------
#         # frappe.msgprint(_("⚠️ Duplicate validation temporarily disabled."), alert=True)
#         return

# class ATMLeads(Document):

#     def validate(self):
#         self.validate_lead_state()

#     # def before_save(self):
#     #   self.validate_lead_state()

#     def validate_lead_state(self):
#         if not self.company:
#             frappe.throw(_("Please select a company before saving the lead."), title=_("Company Not Selected"))

#         if not self.address:
#             frappe.throw(_("Please enter a valid address."), title=_("Address Required"))

#         # Validate company exists
#         company = frappe.get_doc('Operator Companies', self.company)
#         if not company:
#             frappe.throw(_("The selected company does not exist."), title=_("Invalid Company"))

#         # Check state permission from company
#         permitted_states = company.get("permitted_states")
#         if permitted_states:
#             state_permitted = any(state.state_code == self.state_code for state in permitted_states)
#             if not state_permitted:
#                 frappe.throw (
#                     _("The selected state ({0}) is not allowed for the company {1}.").format(self.state_code, self.company),
#                     title=_("State Not Allowed")
#                 )
#         else:
#             frappe.msgprint(_("No restricted states specified for this company. All states are allowed."), alert=True)

#         # duplication validation process based on three phases
#         # 1. firstly validation should be based on "Installed"
#         # 2. secondly validation should be based on "Signed" status
#         # 3. thirdly validateion should be on other status

#         # 1. check lead existance for validation based on address(location) only for any company.
#         installed_exist = frappe.db.exists("ATM Leads", {
#             "address": self.address,
#             "state": self.state,
#             "state_code": self.state_code,
#             "zip_code": self.zip_code,
#             "city": self.city,
#             "country": self.country,
#             "workflow_state": "Installed",
#             "name": ("!=", self.name)
#         })

#         if installed_exist:
#             # find all leads with other status and try to remove them
#             documents_to_delete = frappe.get_list("ATM Leads", 
#                 filters = {
#                     "address": self.address,
#                     "state": self.state,
#                     "state_code": self.state_code,
#                     "zip_code": self.zip_code,
#                     "city": self.city,
#                     "country": self.country,
#                     "workflow_state": ["in", ["Rejected", "Approved", "Pending", "Draft"]],
#                     "name": ("!=", self.name)
#                 }
#             )

#             for doc in documents_to_delete:
#                 frappe.delete_doc("ATM Leads", doc.name)

#             frappe.db.commit()
            
#             frappe.throw(
#                 _("❗ A lead already exists for the same address in a 'Installed' Lead."),
#                 title=_("Duplicate location")
#             )

#         # 2. check lead existance for validation based on address(location) and company.
#         signed_exist = frappe.db.exists("ATM Leads", {
#             "address": self.address,
#             "company": self.company,
#             "state": self.state,
#             "state_code": self.state_code,
#             "zip_code": self.zip_code,
#             "city": self.city,
#             "country": self.country,
#             "workflow_state": "Signed",
#             "name": ("!=", self.name)
#         })

#         if signed_exist:
#             # find all leads with other status and try to remove them
#             documents_to_delete = frappe.get_list("ATM Leads", 
#                 filters = {
#                     "address": self.address,
#                     "company": self.company,
#                     "state": self.state,
#                     "state_code": self.state_code,
#                     "zip_code": self.zip_code,
#                     "city": self.city,
#                     "country": self.country,
#                     "workflow_state": ["in", ["Rejected", "Re Approval", "Agreement Sent", "Approved", "Pending", "Draft"]],
#                     "name": ("!=", self.name)
#                 }
#             )

#             for doc in documents_to_delete:
#                 frappe.delete_doc("ATM Leads", doc.name)

#             frappe.db.commit()
            
#             frappe.throw(
#                 _("❗ A lead already exists for the same address in a 'Signed' Lead."),
#                 title=_("Duplicate location")
#             )
       
#         # 3. check lead existance for validation, based on address(location) and company with other status.
#         other_status_exist = frappe.db.exists("ATM Leads", {
#             "address": self.address,
#             "company": self.company,
#             "state": self.state,
#             "state_code": self.state_code,
#             "zip_code": self.zip_code,
#             "city": self.city,
#             "country": self.country,
#             "workflow_state": ["in", ["Rejected", "Re Approval", "Agreement Sent", "Approved", "Pending", "Draft"]],
#             "name": ("!=", self.name)
#         })

#         if other_status_exist:
            
#             frappe.throw(
#                 _("❗ A lead already exists for the same address in another status."),
#                 title=_("Duplicate location")
#             )


@frappe.whitelist()
def validate(doc, method):
    if not doc.latitude or not doc.longitude:
        if doc.full_address:
            # Geocode using Google Maps API
            try:
                from urllib.parse import urlencode
                api_key = frappe.db.get_single_value("Google Maps Settings", "api_key")  # Store API key in Settings Doctype
                base_url = "https://maps.googleapis.com/maps/api/geocode/json?"
                params = urlencode({'address': doc.full_address, 'key': api_key})
                url = base_url + params
                response = requests.get(url)
                data = response.json()

                if data['status'] == 'OK':
                    location = data['results'][0]['geometry']['location']
                    doc.latitude = location['lat']
                    doc.longitude = location['lng']
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), "ATM Leads Geocode Error")
