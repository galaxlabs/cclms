# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.utils import now
from frappe.utils import date_diff, nowdate
from frappe.model.document import Document
from frappe.utils import date_diff, today


class ATMLeads(Document):
    import frappe
from frappe import _

class ATMLEADS(frappe.model.document.Document):
    def validate(self):
        self.validate_lead_state()

    def validate_lead_state(self):
        # Check if the company is selected
        if not self.company:
            frappe.throw(
                _("Please select a company before saving the lead."),
                title=_("Company Not Selected")
            )

        # Fetch the operator company details
        company = frappe.get_doc('Operator Companies', self.company)

        # Ensure the company exists
        if not company:
            frappe.throw(
                _("The selected company does not exist."),
                title=_("Invalid Company")
            )

        # Access the permitted states from the child table
        permitted_states = company.state_name  # This is the child table containing permitted states

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
            # If the child table is empty, allow all states
            frappe.msgprint(
                _("No restricted states specified for the selected company. All states are allowed."),
                alert=True
            )

    # def validate(self):
    #     self.validate_lead_state_and_business_type()

    # def validate_lead_state_and_business_type(self):
    #     # Check if the company is selected
    #     if not self.company:
    #         frappe.throw(
    #             _("Please select a company before saving the lead."),
    #             title=_("Company Not Selected")
    #         )

    #     # Fetch operator company details
    #     company = frappe.get_doc('Operator Companies', self.company)

    #     # Ensure the company exists
    #     if not company:
    #         frappe.throw(
    #             _("The selected company does not exist."),
    #             title=_("Invalid Company")
    #         )

    #     # Check if the state is restricted
    #     if company.state_name and len(company.state_name) > 0:
    #         state_permitted = any(
    #             state.state_code == self.state_code
    #             for state in company.state_name
    #         )
    #         if not state_permitted:
    #             frappe.throw(
    #                 _("The selected state ({0}) is not allowed for the company {1}. Please select a valid state.").format(self.state_code, self.company),
    #                 title=_("State Not Allowed")
    #             )

    #     # Check if the business type is restricted
    #     if company.restricted_type and len(company.restricted_type) > 0:
    #         business_restricted = any(
    #             restricted.business_type == self.business_type
    #             for restricted in company.restricted_type
    #         )
    #         if business_restricted:
    #             frappe.throw(
    #                 _("The selected business type ({0}) is restricted for the company {1}. Please select a different business type.").format(self.business_type, self.company),
    #                 title=_("Business Type Not Allowed")
    #             )


    # def validate(self):
    #     self.validate_lead_state_code()

    # def validate_lead_state_code(self):
    #     # Check if company is selected
    #     if not self.company:
    #         frappe.throw(
    #             _("Please select a company before saving the lead."),
    #             title=_("Company Not Selected")
    #         )

    #     # Fetch permitted states linked to the selected company
    #     try:
    #         permitted_states = frappe.get_all(
    #             "Permitted States",  # Child Doctype name for permitted states
    #             filters={
    #                 'parent': self.company  # Filter based on the selected company in the lead
    #             },
    #             fields=['state_code'],  # Fields to validate against (only state_code)
    #             ignore_permissions=True  # Bypass permission check
    #         )

    #         frappe.logger().info(f"Fetched permitted states for {self.company}: {permitted_states}")

    #         # Validate lead's state code against the permitted states
    #         if permitted_states:
    #             # Check if any permitted state code matches the lead's state_code
    #             is_permitted = any(
    #                 d['state_code'] == self.state_code
    #                 for d in permitted_states
    #             )

    #             # Restrict if the lead's state code does not match permitted states
    #             if not is_permitted:
    #                 frappe.throw(
    #                     _("This lead is not qualified for the selected operator because the state code is not permitted."),
    #                     title=_("Not Qualified")
    #                 )
    #         else:
    #             # If the permitted states table is empty, allow all state codes
    #             frappe.msgprint(
    #                 _("No permitted state codes specified for the selected company. All state codes are allowed."),
    #                 alert=True
    #             )

    #     except frappe.PermissionError as e:
    #         frappe.throw(_("You do not have permission to access Permitted States: {0}").format(str(e)))
    #     except Exception as e:
    #         frappe.throw(_("An unexpected error occurred: {0}").format(str(e)))
    # def validate(self):
    #     self.validate_lead_state()

    # def validate_lead_state(self):
    #     # Check if company is selected
    #     if not self.company:
    #         frappe.throw(
    #             _("Please select a company before saving the lead."),
    #             title=_("Company Not Selected")
    #         )
        
    #     # Fetch permitted states linked to the selected company
    #     try:
    #         permitted_states = frappe.get_all(
    #             "Permitted States",  # Child Doctype name for permitted states
    #             filters={
    #                 'parent': self.company  # Filter based on the selected company in the lead
    #             },
    #             fields=['state', 'state_code'],  # Fields to validate against
    #             ignore_permissions=True  # Bypass permission check
    #         )

    #         frappe.logger().info(f"Fetched permitted states for {self.company}: {permitted_states}")

    #         # Validate lead state or state code against the permitted states
    #         if permitted_states:
    #             # Check if any permitted state matches the lead's state or state code
    #             is_permitted = any(
    #                 (d['state'] == self.state or d['state_code'] == self.state_code)
    #                 for d in permitted_states
    #             )

    #             # Restrict if the lead's state or state code does not match permitted states
    #             if not is_permitted:
    #                 frappe.throw(
    #                     _("This lead is not qualified for the selected operator because the state or state code is not permitted."),
    #                     title=_("Not Qualified")
    #                 )
    #         else:
    #             # If the permitted states table is empty, allow all states
    #             frappe.msgprint(
    #                 _("No permitted states specified for the selected company. All states are allowed."),
    #                 alert=True
    #             )

    #     except frappe.PermissionError as e:
    #         frappe.throw(_("You do not have permission to access Permitted States: {0}").format(str(e)))
    #     except Exception as e:
    #         frappe.throw(_("An unexpected error occurred: {0}").format(str(e)))

    


    # def update_days(doc, method):
    #     # Check if Approved Date is set and calculate Approved Days
    #     if doc.approve_date:
    #         # Calculate days from Approved Date to Agreement Sent Date or today's date
    #         if doc.agreement_sent_date:
    #             doc.approved_days = date_diff(doc.agreement_sent_date, doc.approve_date)
    #         else:
    #             doc.approved_days = date_diff(nowdate(), doc.approve_date)
    #     else:
    #         doc.approved_days = 0  # No approval date set

    #     # Check if Agreement Sent Date is set and calculate Agreement Sent Days
    #     if doc.agreement_sent_date:
    #         # Calculate days from Agreement Sent Date to Sign Date or today's date
    #         if doc.sign_date:
    #             doc.agreement_sent_days = date_diff(doc.sign_date, doc.agreement_sent_date)
    #         else:
    #             doc.agreement_sent_days = date_diff(nowdate(), doc.agreement_sent_date)
    #     else:
    #         doc.agreement_sent_days = 0  # No agreement sent date set

    #     # Check if Sign Date is set and calculate Sign Days
    #     if doc.sign_date:
    #         doc.sign_days = date_diff(nowdate(), doc.sign_date)
    #     else:
    #         doc.sign_days = 0  # No sign date set

    #     # Stop counting days once next action is taken
    #     # For each count, if the next action is taken, the count should be kept static.
    #     # For Approved Days:
    #     if doc.agreement_sent_date and doc.approve_date:
    #         doc.approved_days = date_diff(doc.agreement_sent_date, doc.approve_date)

    #     # For Agreement Sent Days:
    #     if doc.sign_date and doc.agreement_sent_date:
    #         doc.agreement_sent_days = date_diff(doc.sign_date, doc.agreement_sent_date)

    #     # For Sign Days:
    #     # Sign days count continuously from sign date until stopped manually or by another business logic.

    #     # Save the document to reflect the updated days count
    #     doc.save()

# Hook this function in your Doctype's validate or on_update event
# frappe.whitelist()
# def on_update(doc, method):
#     update_days(doc, method)
