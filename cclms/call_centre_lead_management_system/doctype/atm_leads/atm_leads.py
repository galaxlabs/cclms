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
        # Check for existing Lead and Address, then decide to create or update
        crm_lead = self.create_or_update_crm_lead()
        address = self.create_or_update_address(crm_lead.name)
        contact = self.create_or_update_contact(crm_lead.name)

        # Link ATM Leads to Contact and Address
        self.link_lead_with_contact_and_address(self.name, contact.name, address.name)

    def create_or_update_crm_lead(self):
        # Check if a lead exists based on email and owner name
        lead_exists = frappe.db.exists('Lead', {'lead_name': self.owner_name, 'email_id': self.email})
        primary_phone, whatsapp_phone = self.get_contact_phones()

        if lead_exists:
            # Update existing lead if major address details are the same
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
            # Create a new lead if no matching lead exists
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

    def create_or_update_address(self, lead_name):
        # Check for existing address by title and type
        address_exists = frappe.db.exists('Address', {
            'address_title': self.business_name,
            'address_type': 'Office'
        })

        if address_exists:
            address_doc = frappe.get_doc('Address', {
                'address_title': self.business_name,
                'address_type': 'Office'
            })

            # Update address if only minor fields like city or state changed
            if self.address_has_changed(address_doc):
                address_doc.city = self.city
                address_doc.state = self.state
                address_doc.save(ignore_permissions=True)
                frappe.msgprint(f'Address {address_doc.name} updated successfully!')
        else:
            # Create a new address if no existing one matches
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

    def create_or_update_contact(self, lead_name):
        # Look for an existing contact by name
        contact_exists = frappe.db.exists('Contact', {
            'first_name': self.owner_name.split()[0],
            'last_name': self.owner_name.split()[-1]
        })

        if contact_exists:
            contact_doc = frappe.get_doc('Contact', {
                'first_name': self.owner_name.split()[0],
                'last_name': self.owner_name.split()[-1]
            })

            # Update contact with new emails and phones if available
            self.add_or_update_email(contact_doc)
            self.add_or_update_phone(contact_doc)

            contact_doc.job_title = 'Owner'
            contact_doc.designation = self.business_type
            contact_doc.save(ignore_permissions=True)
            frappe.msgprint(f'Contact {contact_doc.name} updated successfully!')
        else:
            # Create a new contact if none exists
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

            # Add emails and phones
            self.add_or_update_email(contact_doc)
            self.add_or_update_phone(contact_doc)

            contact_doc.insert(ignore_permissions=True)
            frappe.msgprint(f'Contact {contact_doc.name} created successfully!')

        return contact_doc

    def add_or_update_email(self, contact_doc):
        existing_emails = [email.email_id for email in contact_doc.email_ids]

        if self.email and self.email not in existing_emails:
            contact_doc.append('email_ids', {
                'email_id': self.email,
                'is_primary': 1  # Set as primary email
            })

    def add_or_update_phone(self, contact_doc):
        existing_phones = [phone.phone for phone in contact_doc.phone_nos]

        # Determine primary phone from personal or business
        primary_phone = self.personal_cell_phone if self.personal_cell_phone else self.business_phone_number

        # Add primary phone if not already in the list
        if primary_phone and primary_phone not in existing_phones:
            contact_doc.append('phone_nos', {
                'phone': primary_phone,
                'is_primary_mobile_no': 1 if self.personal_cell_phone else 0,  # Primary if it's a mobile
                'is_primary_phone': 1 if not self.personal_cell_phone else 0   # Primary if it's a business phone
            })

        # Add secondary phone if exists and it's different from the primary
        secondary_phone = self.business_phone_number if self.personal_cell_phone else None
        if secondary_phone and secondary_phone not in existing_phones:
            contact_doc.append('phone_nos', {
                'phone': secondary_phone,
                'is_primary_phone': 0  # Not primary
            })

    def link_lead_with_contact_and_address(self, atm_lead_name, contact_name, address_name):
        # Link ATM Leads with Contact and Address through dynamic links
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

    def address_has_changed(self, doc):
        # Check if the major details of the address have changed
        return (
            doc.address_line1 != self.address or
            doc.city != self.city or
            doc.state != self.state or
            doc.country != self.country or
            doc.pincode != self.zippostal_code
        )

    def get_contact_phones(self):
        primary_phone = self.personal_cell_phone if self.personal_cell_phone else self.business_phone_number
        return primary_phone, None  # Assuming only primary phone is tracked for WhatsApp, adjust if needed

    def get_primary_phone(self):
        return self.get_contact_phones()[0]
    


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

