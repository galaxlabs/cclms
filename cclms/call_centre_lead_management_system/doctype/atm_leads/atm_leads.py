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
            # Create or update contact
            contact = self.create_or_update_contact()

            # Create or update address
            address = self.create_or_update_address()

            # Create or update lead
            lead = self.create_or_update_lead(contact.name, address.name)

            # Link ATM Leads to Contact and Address
            self.link_lead_with_contact_and_address(lead.name, contact.name, address.name)
            
        except Exception as e:
            frappe.msgprint(f"An error occurred while updating the ATM Leads. Please check logs for details.")

    def create_or_update_contact(self):
        contact_exists = frappe.db.exists('Contact', {'email_ids': self.email})

        if contact_exists:
            contact_doc = frappe.get_doc('Contact', contact_exists)
            contact_doc.first_name = self.owner_name.split()[0]
            contact_doc.last_name = self.owner_name.split()[-1]
            self.add_or_update_email(contact_doc)
            self.add_or_update_phone(contact_doc)
            contact_doc.save(ignore_permissions=True)
            frappe.msgprint(f'Contact {contact_doc.name} updated successfully!')
        else:
            contact_doc = frappe.get_doc({
                'doctype': 'Contact',
                'first_name': self.owner_name.split()[0],
                'last_name': self.owner_name.split()[-1],
                'email_ids': [{'email_id': self.email}],
                'phone_nos': [{'phone': self.personal_cell_phone, 'is_primary_mobile_no': 1}] if self.personal_cell_phone else [],
                'links': [{'link_doctype': 'ATM Leads', 'link_name': self.name}]
            })
            contact_doc.insert(ignore_permissions=True)
            frappe.msgprint(f'Contact {contact_doc.name} created successfully!')

        return contact_doc

    def create_or_update_address(self):
        address_exists = frappe.db.exists('Address', {
            'address_line1': self.address,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'pincode': self.zippostal_code
        })

        if address_exists:
            address_doc = frappe.get_doc('Address', address_exists)
            address_doc.address_title = self.business_name
            address_doc.address_type = 'Office'
            address_doc.is_shipping_address = 1  # Set as default shipping address
            address_doc.save(ignore_permissions=True)
            frappe.msgprint(f'Address {address_doc.name} updated successfully!')
        else:
            address_doc = frappe.get_doc({
                'doctype': 'Address',
                'address_title': self.business_name,
                'address_line1': self.address,
                'city': self.city,
                'state': self.state,
                'country': self.country,
                'pincode': self.zippostal_code,
                'address_type': 'Office',
                'is_shipping_address': 1,  # Set as default shipping address
                'links': [{'link_doctype': 'ATM Leads', 'link_name': self.name}]
            })
            address_doc.insert(ignore_permissions=True)
            frappe.msgprint(f'Address {address_doc.name} created successfully!')

        return address_doc

    def create_or_update_lead(self, contact_name, address_name):
        lead_exists = frappe.db.exists('Lead', {'email_id': self.email})

        if lead_exists:
            lead_doc = frappe.get_doc('Lead', lead_exists)
            lead_doc.lead_name = self.owner_name
            lead_doc.company_name = self.business_name
            lead_doc.save(ignore_permissions=True)
            frappe.msgprint(f'Lead {lead_doc.name} updated successfully!')
        else:
            lead_doc = frappe.get_doc({
                'doctype': 'Lead',
                'lead_name': self.owner_name,
                'company_name': self.business_name,
                'email_id': self.email,
                'status': 'Lead',
                'lead_owner': self.owner,
                'links': [
                    {'link_doctype': 'Contact', 'link_name': contact_name},
                    {'link_doctype': 'Address', 'link_name': address_name}
                ]
            })
            lead_doc.insert(ignore_permissions=True)
            frappe.msgprint(f'Lead {lead_doc.name} created successfully!')

        return lead_doc

    def link_lead_with_contact_and_address(self, lead_name, contact_name, address_name):
        # Ensure linkage in Dynamic Link table
        self.link_doctype_with_dynamic_link(lead_name, contact_name, 'Contact')
        self.link_doctype_with_dynamic_link(lead_name, address_name, 'Address')

    def link_doctype_with_dynamic_link(self, parent_name, link_name, link_doctype):
        existing_links = frappe.get_all('Dynamic Link', filters={
            'link_doctype': link_doctype,
            'link_name': link_name,
            'parenttype': 'Lead',
            'parent': parent_name
        })

        if len(existing_links) == 0:
            link_doc = frappe.get_doc({
                'doctype': 'Dynamic Link',
                'parent': parent_name,
                'parenttype': 'Lead',
                'link_doctype': link_doctype,
                'link_name': link_name
            })
            link_doc.insert(ignore_permissions=True)

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
