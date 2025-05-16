# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.utils import date_diff, nowdate
from frappe.model.document import Document

#from frappe.utils import today, add_days

import datetime
from datetime import timedelta

class ATMLeads(Document):

    def validate(self):
        self.validate_lead_state()

    # def before_save(self):
    #   self.validate_lead_state()

    def validate_lead_state(self):        
        if not self.company:
            frappe.throw(
                _("Please select a company before saving the lead."),
                title=_("Company Not Selected")
            )
        if not self.address:
            frappe.throw(
                _("Please enter valid address."),
                title=_("Address required")
            )

        # Fetch the operator company details
        company = frappe.get_doc('Operator Companies', self.company)

        if not company:
            frappe.throw(
                _("The selected company does not exist."),
                title=_("Invalid Company")
            )

        # Access the permitted states from the child table
        permitted_states = company.get("permitted_states")  # Assuming child table is named "permitted_states"

        if permitted_states:
            # Check if the lead's state_code is in the permitted states
            state_permitted = any(
                state.state_code == self.state_code
                for state in permitted_states
            )
            if not state_permitted:
                frappe.throw(
                    _("The selected state ({0}) is not allowed for the company {1}. Please select a valid state.").format(self.state_code, self.company),
                    title=_("State Not Allowed")
                )
        else:
            frappe.msgprint(
                _("No restricted states specified for the selected company. All states are allowed."),
                alert=True
            )

        # validate lead against duplicate location with workflow_state
        
        installed_leads_count = self.get_leads_count_by_workflow_state("Installed", 0)
        signed_leads_count = self.get_leads_count_by_workflow_state("Signed", 0)
        rejected_leads_count = self.get_leads_count_by_workflow_state("Rejected", 90)
        approved_leads_count = self.get_leads_count_by_workflow_state("Approved", 30)
        pending_leads_count = self.get_leads_count_by_workflow_state("Pending", 30)
        draft_leads_count = self.get_leads_count_by_workflow_state("Draft", 7)

        #frappe.throw("Installed:" + str(installed_leads_count) + ", Rejected:" + str(rejected_leads_count) + ", Approved:" + str(approved_leads_count) + ", Pending:" + str(pending_leads_count) + ", Draft:" + str(draft_leads_count), title="Counting")

        if installed_leads_count > 0:
            frappe.throw(
                _("Some leads are already exist in Installed for the selected company and location"),
                title=_("Duplicate Location Error")
            )

        if rejected_leads_count > 0:
            frappe.throw(
                _("Some leads are already exist in Rejected for the selected company and location"),
                title=_("Duplicate Location Error")
            )

        if approved_leads_count > 0:
            frappe.throw(
                _("Some leads are already exist in Approved for the selected company and location"),
                title=_("Duplicate Location Error")
            )

        if pending_leads_count > 0:
            frappe.throw(
                _("Some leads are already exist in Pending for the selected company and location"),
                title=_("Duplicate Location Error")
            )

        if draft_leads_count > 0:
            frappe.throw(
                _("Some leads are already exist in Draft for the selected company and location"),
                title=_("Duplicate Location Error")
            )

    #get lead counts by workflow_state with date span
    def get_leads_count_by_workflow_state(self, workflow_state, number_of_days):
        leads_count = 0
        today = datetime.date.today()
        delta = timedelta(days = number_of_days)
        abstracted_date = today - delta

        if workflow_state == "Installed":
            doc_filters = {"company":self.company, "address": self.address, "workflow_state": workflow_state}
            leads_count = frappe.db.count("ATM Leads", filters = doc_filters)
        elif workflow_state == "Signed":            
            doc_filters = {"company":self.company, "address": self.address, "workflow_state": workflow_state}
            leads_count = frappe.db.count("ATM Leads", filters = doc_filters)
        elif workflow_state == "Approved":            
            doc_filters = {"company":self.company, "address": self.address, "workflow_state": workflow_state}
            leads_count = frappe.db.count("ATM Leads", filters = doc_filters)
        else:            
            # doc_filters = {"company":self.company, "address": self.address, "workflow_state": workflow_state, "post_date":['<', abstracted_date]}
            doc_filters = {"company":self.company, "address": self.address, "workflow_state": workflow_state}
            leads_count = frappe.db.count("ATM Leads", filters = doc_filters)

        return leads_count
