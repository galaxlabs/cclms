# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.utils import now
from frappe.utils import date_diff, nowdate
from frappe.model.document import Document
from frappe.utils import date_diff, today


class ATMLeads(Document):
    def validate(self):
        self.validate_lead_state()

    def validate_lead_state(self):
        # Check if company is selected
        if not self.company:
            frappe.throw(
                _("Please select a company before saving the lead."),
                title=_("Company Not Selected")
            )
        
        # Fetch permitted states linked to the selected company
        try:
            permitted_states = frappe.get_all(
                "Permitted States",  # Child Doctype name for permitted states
                filters={
                    'parent': self.company  # Filter based on the selected company in the lead
                },
                fields=['state', 'state_code'],  # Fields to validate against
                ignore_permissions=True  # Bypass permission check
            )

            frappe.logger().info(f"Fetched permitted states for {self.company}: {permitted_states}")

            # Validate lead state or state code against the permitted states
            if permitted_states:
                # Check if any permitted state matches the lead's state or state code
                is_permitted = any(
                    (d['state'] == self.state or d['state_code'] == self.state_code)
                    for d in permitted_states
                )

                # Restrict if the lead's state or state code does not match permitted states
                if not is_permitted:
                    frappe.throw(
                        _("This lead is not qualified for the selected operator because the state or state code is not permitted."),
                        title=_("Not Qualified")
                    )
            else:
                # If the permitted states table is empty, allow all states
                frappe.msgprint(
                    _("No permitted states specified for the selected company. All states are allowed."),
                    alert=True
                )

        except frappe.PermissionError as e:
            frappe.throw(_("You do not have permission to access Permitted States: {0}").format(str(e)))
        except Exception as e:
            frappe.throw(_("An unexpected error occurred: {0}").format(str(e)))

# Function to calculate and update days for each lead
def update_lead_days():
    # Get all ATM Leads that need their days fields updated
    leads = frappe.get_all("ATM Leads", filters={}, fields=["name"])

    for lead in leads:
        # Fetch the document
        doc = frappe.get_doc("ATM Leads", lead['name'])

        # Calculate days for each relevant field
        calculate_days_for_lead(doc)

# Function to calculate days for each date field and update the document
def calculate_days_for_lead(doc):
    # Calculate approved_days
    if doc.approve_date:
        doc.approved_days = date_diff(today(), doc.approve_date)
    else:
        doc.approved_days = 0

    # Calculate agreement_sent_days
    if doc.agreement_sent_date:
        doc.agreement_sent_days = date_diff(today(), doc.agreement_sent_date)
    else:
        doc.agreement_sent_days = 0

    # Calculate sign_days
    if doc.sign_date:
        doc.sign_days = date_diff(today(), doc.sign_date)
    else:
        doc.sign_days = 0

    # Calculate convert_days
    if doc.convert_date:
        doc.convert_days = date_diff(today(), doc.convert_date)
    else:
        doc.convert_days = 0

    # Calculate install_days
    if doc.install_date:
        doc.install_days = date_diff(today(), doc.install_date)
    else:
        doc.install_days = 0

    # Calculate remove_days
    if doc.remove_date:
        doc.remove_days = date_diff(today(), doc.remove_date)
    else:
        doc.remove_days = 0

    # Save the document
    doc.save()


#     def update_days(doc):
#     # Check if Approved Date is set and calculate Approved Days
#         if doc.approve_date:
#             if doc.agreement_sent_date:
#                 doc.approved_days = date_diff(doc.agreement_sent_date, doc.approve_date)
#             else:
#                 doc.approved_days = date_diff(nowdate(), doc.approve_date)
#         else:
#             doc.approved_days = 0

#         # Check if Agreement Sent Date is set and calculate Agreement Sent Days
#         if doc.agreement_sent_date:
#             if doc.sign_date:
#                 doc.agreement_sent_days = date_diff(doc.sign_date, doc.agreement_sent_date)
#             else:
#                 doc.agreement_sent_days = date_diff(nowdate(), doc.agreement_sent_date)
#         else:
#             doc.agreement_sent_days = 0

#         # Check if Sign Date is set and calculate Sign Days
#         if doc.sign_date:
#             doc.sign_days = date_diff(nowdate(), doc.sign_date)
#         else:
#             doc.sign_days = 0

#         # Calculate Convert Days
#         if doc.convert_date:
#             doc.convert_days = date_diff(nowdate(), doc.convert_date)
#         else:
#             doc.convert_days = 0

#         # Calculate Install Days
#         if doc.install_date:
#             doc.install_days = date_diff(nowdate(), doc.install_date)
#         else:
#             doc.install_days = 0

#         # Calculate Remove Days
#         if doc.remove_date:
#             doc.remove_days = date_diff(nowdate(), doc.remove_date)
#         else:
#             doc.remove_days = 0

#         # Save the document to persist changes
#         doc.save(ignore_permissions=True)

# def update_all_leads():
#     # Get all leads in ATMLeads Doctype
#     leads = frappe.get_all('ATM Leads', fields=['name'])

#     for lead in leads:
#         # Fetch each document
#         doc = frappe.get_doc('ATM Leads', lead['name'])

#         # Update the days for each document
#         update_days(doc)

#     # Commit the changes to the database
#     frappe.db.commit()

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
frappe.whitelist()
def on_update(doc, method):
    update_days(doc, method)
