# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.utils import now
import frappe
from frappe.utils import date_diff, nowdate
from frappe.model.document import Document

class ATMLeads(Document):
    def on_update(self):
        try:
            # Check for existing Lead and Address, then decide to create or update
            crm_lead = self.create_or_update_crm_lead()
            address = self.create_or_update_address(crm_lead.name)
            contact = self.create_or_update_contact(crm_lead.name)
            
            # Handle duplication
            if self.is_duplicate_lead():
                self.handle_duplicate_lead()
                return

            # Link ATM Leads to Contact and Address
            self.link_lead_with_contact_and_address(self.name, contact.name, address.name)

            # Link to Employee, Sales Person, Branch, and User
            self.link_to_employee()
            self.link_to_sales_person()
            self.link_to_branch()
            self.link_to_user()

        except Exception as e:
            frappe.log_error(f"Error updating ATM Leads: {str(e)}", "ATM Leads Update Error")
            frappe.msgprint(f"An error occurred while updating the ATM Leads. Please check logs for details.")

    def is_duplicate_lead(self):
        # Check for duplicate leads based on address, email, phone, etc.
        existing_leads = frappe.get_all('Lead', filters={
            'address_line1': self.address,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'pincode': self.zippostal_code,
            'email_id': self.email,
            'mobile_no': self.personal_cell_phone or self.business_phone_number
        })
        return len(existing_leads) > 0

    def handle_duplicate_lead(self):
        # Handle duplicate leads (e.g., move to queue, log message, etc.)
        frappe.msgprint("This lead is a duplicate and has been moved to the queue.")
        self.add_to_queue()  # Implement this method to handle queue logic

    def add_to_queue(self):
        # Implement logic to add the lead to a queue for further review
        pass

    def create_or_update_crm_lead(self):
        try:
            lead_exists = frappe.db.exists('Lead', {'lead_name': self.owner_name, 'email_id': self.email})
            primary_phone, whatsapp_phone = self.get_contact_phones()

            if lead_exists:
                lead_doc = frappe.get_doc('Lead', {'lead_name': self.owner_name, 'email_id': self.email})
                if self.address_has_changed(lead_doc):
                    lead_doc.address_line1 = self.address
                    lead_doc.city = self.city
                    lead_doc.state = self.state
                    lead_doc.country = self.country
                    lead_doc.pincode = self.zippostal_code
                    lead_doc.save(ignore_permissions=True)
                    frappe.msgprint(f'Lead {lead_doc.name} updated successfully!')
            else:
                lead_doc = frappe.get_doc({
                    'doctype': 'Lead',
                    'lead_name': self.owner_name,
                    'company_name': self.business_name,
                    'email_id': self.email,
                    'mobile_no': primary_phone,
                    'whatsapp_no': whatsapp_phone,
                    'status': 'Lead',
                    'lead_owner': self.owner
                })
                lead_doc.insert(ignore_permissions=True)
                frappe.msgprint(f'Lead {lead_doc.name} created successfully!')

            return lead_doc
        except Exception as e:
            frappe.log_error(f"Error creating or updating CRM Lead: {str(e)}", "CRM Lead Error")
            frappe.msgprint(f"An error occurred while processing the CRM Lead. Please check logs for details.")

    def create_or_update_address(self, lead_name):
        try:
            address_exists = frappe.db.exists('Address', {
                'address_title': self.business_name,
                'address_type': 'Office'
            })

            if address_exists:
                address_doc = frappe.get_doc('Address', {
                    'address_title': self.business_name,
                    'address_type': 'Office'
                })

                if self.address_has_changed(address_doc):
                    address_doc.city = self.city
                    address_doc.state = self.state
                    address_doc.save(ignore_permissions=True)
                    frappe.msgprint(f'Address {address_doc.name} updated successfully!')
            else:
                address_doc = frappe.get_doc({
                    'doctype': 'Address',
                    'address_title': self.business_name,
                    'address_type': 'Office',
                    'address_line1': self.address,
                    'city': self.city,
                    'state': self.state,
                    'country': self.country,
                    'pincode': self.zippostal_code,
                    'email_id': self.email,
                    'phone': self.get_primary_phone(),
                    'links': [{
                        'link_doctype': 'Lead',
                        'link_name': lead_name
                    }]
                })
                address_doc.insert(ignore_permissions=True)
                frappe.msgprint(f'Address {address_doc.name} created successfully!')

            return address_doc
        except Exception as e:
            frappe.log_error(f"Error creating or updating Address: {str(e)}", "Address Error")
            frappe.msgprint(f"An error occurred while processing the Address. Please check logs for details.")

    def create_or_update_contact(self, lead_name):
        try:
            contact_exists = frappe.db.exists('Contact', {
                'first_name': self.owner_name.split()[0],
                'last_name': self.owner_name.split()[-1]
            })

            if contact_exists:
                contact_doc = frappe.get_doc('Contact', {
                    'first_name': self.owner_name.split()[0],
                    'last_name': self.owner_name.split()[-1]
                })

                self.add_or_update_email(contact_doc)
                self.add_or_update_phone(contact_doc)

                contact_doc.job_title = 'Owner'
                contact_doc.designation = self.business_type
                contact_doc.save(ignore_permissions=True)
                frappe.msgprint(f'Contact {contact_doc.name} updated successfully!')
            else:
                contact_doc = frappe.get_doc({
                    'doctype': 'Contact',
                    'first_name': self.owner_name.split()[0],
                    'last_name': self.owner_name.split()[-1],
                    'company_name': self.business_name,
                    'job_title': 'Owner',
                    'designation': self.business_type,
                    'links': [{
                        'link_doctype': 'Lead',
                        'link_name': lead_name
                    }]
                })

                self.add_or_update_email(contact_doc)
                self.add_or_update_phone(contact_doc)

                contact_doc.insert(ignore_permissions=True)
                frappe.msgprint(f'Contact {contact_doc.name} created successfully!')

            return contact_doc
        except Exception as e:
            frappe.log_error(f"Error creating or updating Contact: {str(e)}", "Contact Error")
            frappe.msgprint(f"An error occurred while processing the Contact. Please check logs for details.")

    def add_or_update_email(self, contact_doc):
        try:
            existing_emails = [email.email_id for email in contact_doc.email_ids]

            if self.email and self.email not in existing_emails:
                contact_doc.append('email_ids', {
                    'email_id': self.email,
                    'is_primary': 1
                })
        except Exception as e:
            frappe.log_error(f"Error adding or updating email for Contact: {str(e)}", "Contact Email Error")

    def add_or_update_phone(self, contact_doc):
        try:
            existing_phones = [phone.phone for phone in contact_doc.phone_nos]

            primary_phone = self.personal_cell_phone if self.personal_cell_phone else self.business_phone_number

            if primary_phone and primary_phone not in existing_phones:
                contact_doc.append('phone_nos', {
                    'phone': primary_phone,
                    'is_primary_mobile_no': 1 if self.personal_cell_phone else 0,
                    'is_primary_phone': 1 if not self.personal_cell_phone else 0
                })

            secondary_phone = self.business_phone_number if self.personal_cell_phone else None
            if secondary_phone and secondary_phone not in existing_phones:
                contact_doc.append('phone_nos', {
                    'phone': secondary_phone,
                    'is_primary_phone': 0
                })
        except Exception as e:
            frappe.log_error(f"Error adding or updating phone for Contact: {str(e)}", "Contact Phone Error")

    def link_lead_with_contact_and_address(self, atm_lead_name, contact_name, address_name):
        try:
            if not frappe.db.exists('Dynamic Link', {'parent': atm_lead_name, 'link_name': contact_name, 'link_doctype': 'Contact'}):
                frappe.get_doc({
                    'doctype': 'Dynamic Link',
                    'parenttype': 'ATM Leads',
                    'parent': atm_lead_name,
                    'link_doctype': 'Contact',
                    'link_name': contact_name
                }).insert(ignore_permissions=True)

            if not frappe.db.exists('Dynamic Link', {'parent': atm_lead_name, 'link_name': address_name, 'link_doctype': 'Address'}):
                frappe.get_doc({
                    'doctype': 'Dynamic Link',
                    'parenttype': 'ATM Leads',
                    'parent': atm_lead_name,
                    'link_doctype': 'Address',
                    'link_name': address_name
                }).insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error linking Lead with Contact and Address: {str(e)}", "Link Error")

    def link_to_employee(self):
        try:
            if self.employee:
                if not frappe.db.exists('Dynamic Link', {'parent': self.name, 'link_name': self.employee, 'link_doctype': 'Employee'}):
                    frappe.get_doc({
                        'doctype': 'Dynamic Link',
                        'parenttype': 'ATM Leads',
                        'parent': self.name,
                        'link_doctype': 'Employee',
                        'link_name': self.employee
                    }).insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error linking Lead with Employee: {str(e)}", "Employee Link Error")

    def link_to_sales_person(self):
        try:
            if self.sales_person:
                if not frappe.db.exists('Dynamic Link', {'parent': self.name, 'link_name': self.sales_person, 'link_doctype': 'Sales Person'}):
                    frappe.get_doc({
                        'doctype': 'Dynamic Link',
                        'parenttype': 'ATM Leads',
                        'parent': self.name,
                        'link_doctype': 'Sales Person',
                        'link_name': self.sales_person
                    }).insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error linking Lead with Sales Person: {str(e)}", "Sales Person Link Error")

    def link_to_branch(self):
        try:
            if self.branch:
                if not frappe.db.exists('Dynamic Link', {'parent': self.name, 'link_name': self.branch, 'link_doctype': 'Branch'}):
                    frappe.get_doc({
                        'doctype': 'Dynamic Link',
                        'parenttype': 'ATM Leads',
                        'parent': self.name,
                        'link_doctype': 'Branch',
                        'link_name': self.branch
                    }).insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error linking Lead with Branch: {str(e)}", "Branch Link Error")

    def link_to_user(self):
        try:
            if self.user:
                if not frappe.db.exists('Dynamic Link', {'parent': self.name, 'link_name': self.user, 'link_doctype': 'User'}):
                    frappe.get_doc({
                        'doctype': 'Dynamic Link',
                        'parenttype': 'ATM Leads',
                        'parent': self.name,
                        'link_doctype': 'User',
                        'link_name': self.user
                    }).insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error linking Lead with User: {str(e)}", "User Link Error")

    def address_has_changed(self, doc):
        return (
            doc.address_line1 != self.address or
            doc.city != self.city or
            doc.state != self.state or
            doc.country != self.country or
            doc.pincode != self.zippostal_code
        )

    def get_contact_phones(self):
        primary_phone = self.personal_cell_phone if self.personal_cell_phone else self.business_phone_number
        return primary_phone, None

    def get_primary_phone(self):
        return self.get_contact_phones()[0]


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
    # def validate(self):
    #     self.validate_lead_state()

    # def validate_lead_state(self):
    #     if self.company:
    #         try:
    #             # Fetch permitted states linked to the selected company
    #             permitted_states = frappe.get_all(
    #                 "Permitted States",  # Child Doctype name
    #                 filters={
    #                     'parent': self.company  # Filters based on the selected company in the lead
    #                 },
    #                 fields=['state', 'state_code'],  # Fields to validate against
    #                 ignore_permissions=True  # Bypass permission check
    #             )

    #             frappe.logger().info(f"Fetched permitted states for {self.company}: {permitted_states}")

    #             # Check if any permitted state matches the lead's state or state code
    #             if permitted_states:
    #                 is_permitted = any(
    #                     (d['state'] == self.state or d['state_code'] == self.state_code)
    #                     for d in permitted_states
    #                 )

    #                 if not is_permitted:
    #                     frappe.throw(
    #                         _("This lead is not qualified for the selected operator because the state or state code is not permitted."),
    #                         title=_("Not Qualified")
    #                     )
    #             else:
    #                 # If the permitted states table is empty, allow all states
    #                 pass  # Assuming all states are allowed if no permitted states are specified

    #         except frappe.PermissionError as e:
    #             frappe.throw(_("You do not have permission to access Permitted States: {0}").format(str(e)))
    #         except Exception as e:
    #             frappe.throw(_("An unexpected error occurred: {0}").format(str(e)))
    
    #     else:
    #         frappe.throw(
    #             _("Please select a company before saving the lead."),
    #             title=_("Company Not Selected")
    #         )

    def update_days(doc, method):
    # Check if Approved Date is set and calculate Approved Days
        if doc.approve_date:
            # Calculate days from Approved Date to Agreement Sent Date or today's date
            if doc.agreement_sent_date:
                doc.approved_days = date_diff(doc.agreement_sent_date, doc.approve_date)
            else:
                doc.approved_days = date_diff(nowdate(), doc.approve_date)
        else:
            doc.approved_days = 0  # No approval date set

        # Check if Agreement Sent Date is set and calculate Agreement Sent Days
        if doc.agreement_sent_date:
            # Calculate days from Agreement Sent Date to Sign Date or today's date
            if doc.sign_date:
                doc.agreement_sent_days = date_diff(doc.sign_date, doc.agreement_sent_date)
            else:
                doc.agreement_sent_days = date_diff(nowdate(), doc.agreement_sent_date)
        else:
            doc.agreement_sent_days = 0  # No agreement sent date set

        # Check if Sign Date is set and calculate Sign Days
        if doc.sign_date:
            doc.sign_days = date_diff(nowdate(), doc.sign_date)
        else:
            doc.sign_days = 0  # No sign date set

        # Stop counting days once next action is taken
        # For each count, if the next action is taken, the count should be kept static.
        # For Approved Days:
        if doc.agreement_sent_date and doc.approve_date:
            doc.approved_days = date_diff(doc.agreement_sent_date, doc.approve_date)

        # For Agreement Sent Days:
        if doc.sign_date and doc.agreement_sent_date:
            doc.agreement_sent_days = date_diff(doc.sign_date, doc.agreement_sent_date)

        # For Sign Days:
        # Sign days count continuously from sign date until stopped manually or by another business logic.

        # Save the document to reflect the updated days count
        doc.save()

# Hook this function in your Doctype's validate or on_update event
frappe.whitelist()
def on_update(doc, method):
    update_days(doc, method)



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