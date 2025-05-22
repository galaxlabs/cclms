# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt
import frappe
import datetime
from frappe import _
from frappe.utils import date_diff, nowdate
from frappe.model.document import Document
from datetime import timedelta
#from frappe.utils import today, add_days

class ATMLeads(Document):

    def validate(self):
        self.validate_lead_state()

    # def before_save(self):
    #   self.validate_lead_state()

    def validate_lead_state(self):
        if not self.company:
            frappe.throw(_("Please select a company before saving the lead."), title=_("Company Not Selected"))

        if not self.address:
            frappe.throw(_("Please enter a valid address."), title=_("Address Required"))

        # Validate company exists
        company = frappe.get_doc('Operator Companies', self.company)
        if not company:
            frappe.throw(_("The selected company does not exist."), title=_("Invalid Company"))

        # Check state permission from company
        permitted_states = company.get("permitted_states")
        if permitted_states:
            state_permitted = any(state.state_code == self.state_code for state in permitted_states)
            if not state_permitted:
                frappe.throw (
                    _("The selected state ({0}) is not allowed for the company {1}.").format(self.state_code, self.company),
                    title=_("State Not Allowed")
                )
        else:
            frappe.msgprint(_("No restricted states specified for this company. All states are allowed."), alert=True)

        # duplication validation process based on three phases
        # 1. firstly validation should be based on "Installed"
        # 2. secondly validation should be based on "Signed" status
        # 3. thirdly validateion should be on other status

        # 1. check lead existance for validation based on address(location) only for any company.
        installed_exist = frappe.db.exists("ATM Leads", {
            "address": self.address,
            "state": self.state,
            "state_code": self.state_code,
            "zippostal_code": self.zippostal_code,
            "city": self.city,
            "country": self.country,
            "workflow_state": "Installed"
        })

        if installed_exist:
            # find all leads with other status and try to remove them
            documents_to_delete = frappe.get_list("ATM Leads", 
                filters = {
                    "address": self.address,
                    "state": self.state,
                    "state_code": self.state_code,
                    "zippostal_code": self.zippostal_code,
                    "city": self.city,
                    "country": self.country,
                    "workflow_state": ["in", ["Rejected", "Approved", "Pending", "Draft"]]
                }
            )

            for doc in documents_to_delete:
                frappe.delete_doc("ATM Leads", doc.name)

            frappe.db.commit()
            
            frappe.throw(
                _("❗ A lead already exists for the same address in a 'Installed' Lead."),
                title=_("Duplicate location")
            )

        # 2. check lead existance for validation based on address(location) and company.
        signed_exist = frappe.db.exists("ATM Leads", {
            "address": self.address,
            "company": self.company,
            "state": self.state,
            "state_code": self.state_code,
            "zippostal_code": self.zippostal_code,
            "city": self.city,
            "country": self.country,
            "workflow_state": "Signed"
        })

        if signed_exist:
            # find all leads with other status and try to remove them
            documents_to_delete = frappe.get_list("ATM Leads", 
                filters = {
                    "address": self.address,
                    "company": self.company,
                    "state": self.state,
                    "state_code": self.state_code,
                    "zippostal_code": self.zippostal_code,
                    "city": self.city,
                    "country": self.country,
                    "workflow_state": ["in", ["Rejected", "Approved", "Pending", "Draft"]]
                }
            )

            for doc in documents_to_delete:
                frappe.delete_doc("ATM Leads", doc.name)

            frappe.db.commit()
            
            frappe.throw(
                _("❗ A lead already exists for the same address in a 'Signed' Lead."),
                title=_("Duplicate location")
            )
       
        # 3. check lead existance for validation, based on address(location) and company with other status.
        other_status_exist = frappe.db.exists("ATM Leads", {
            "address": self.address,
            "company": self.company,
            "state": self.state,
            "state_code": self.state_code,
            "zippostal_code": self.zippostal_code,
            "city": self.city,
            "country": self.country,
            "workflow_state": ["Rejected", "Re Approval", "Agreement Sent", "Approved", "Pending", "Draft"]
        })

        if other_status_exist:
            
            frappe.throw(
                _("❗ A lead already exists for the same address in another status."),
                title=_("Duplicate location")
            )
