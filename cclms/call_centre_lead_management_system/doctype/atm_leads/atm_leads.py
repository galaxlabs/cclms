# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
from frappe import _
from frappe.utils import now

class ATMLeads(Document):
    def validate(self):
        self.validate_lead_state()

    def validate_lead_state(self):
        if self.company:
            try:
                # Fetch permitted states linked to the selected company
                permitted_states = frappe.get_all(
                    "Permitted States",  # Child Doctype name
                    filters={
                        'parent': self.company  # Filters based on the selected company in the lead
                    },
                    fields=['state', 'state_code'],  # Fields to validate against
                    ignore_permissions=True  # Bypass permission check
                )

                frappe.logger().info(f"Fetched permitted states for {self.company}: {permitted_states}")

                # Check if any permitted state matches the lead's state or state code
                if permitted_states:
                    is_permitted = any(
                        (d['state'] == self.state or d['state_code'] == self.state_code)
                        for d in permitted_states
                    )

                    if not is_permitted:
                        frappe.throw(
                            _("This lead is not qualified for the selected operator because the state or state code is not permitted."),
                            title=_("Not Qualified")
                        )
                else:
                    # If the permitted states table is empty, allow all states
                    pass  # Assuming all states are allowed if no permitted states are specified

            except frappe.PermissionError as e:
                frappe.throw(_("You do not have permission to access Permitted States: {0}").format(str(e)))
            except Exception as e:
                frappe.throw(_("An unexpected error occurred: {0}").format(str(e)))
    
        else:
            frappe.throw(
                _("Please select a company before saving the lead."),
                title=_("Company Not Selected")
            )

# def validate(doc, method):
#     # Fetch the logged-in user's location
#     user_location = frappe.get_value('User', frappe.session.user, 'location')

#     # Check if the document's branch matches the user's location
#     if doc.branch != user_location:
#         frappe.throw(f"You do not have permission to access records from this branch: {doc.branch}")

# def update_dates(doc, method):
#     if doc.workflow_state == "Agreement Sent":
#         doc.agreement_sent_date = now()
#     elif doc.workflow_state == "Approved":
#         doc.approved_date = now()
#     elif doc.workflow_state == "Installed":
#         doc.install_date = now()
#     elif doc.workflow_state == "Signed":
#         doc.signed_date = now()
#     doc.save()

# import frappe
# from frappe.model.document import Document
# from frappe.utils import getdate, today
# from frappe import _

# class Leads(Document):
#     def validate(self):
#         self.validate_lead_state()

#     def validate_lead_state(self):
#         if self.company:
#             # Fetch permitted states linked to the selected company
#             permitted_states = frappe.get_all(
#                 "Permitted States",  # Child Doctype name
#                 filters={
#                     'parent': self.company  # Filters based on the selected company in the lead
#                 },
#                 fields=['state', 'state_code'],  # Fields to validate against
#                 ignore_permissions=True  # Bypass permission check
#             )

#             # Check if any permitted state matches the lead's state or state code
#             if permitted_states:
#                 # Check if any permitted state matches the lead's state or state code
#                 is_permitted = any(
#                     (d['state'] == self.state or d['state_code'] == self.state_code)
#                     for d in permitted_states
#                 )

#                 # If no permitted state matches, raise a ValidationError
#                 if not is_permitted:
#                     frappe.throw(
#                         _("This lead is not qualified for the selected operator because the state or state code is not permitted."),
#                         title=_("Not Qualified")
#                     )
#             else:
#                 # If the permitted states table is empty, allow all states
#                 # This implies the company has permissions for all states, no validation needed
#                 pass  # No action needed

#         else:
#             # If no company is selected, raise a ValidationError
#             frappe.throw(
#                 _("Please select a company before saving the lead."),
#                 title=_("Company Not Selected")
#             )