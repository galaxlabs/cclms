import frappe
from frappe.model.document import Document

class CallingLeads(Document):
    pass
#     def on_update(self):
#         # Create or Update CRM Lead
#         crm_lead = self.create_or_update_crm_lead()

#         # Create or Update Address
#         address = self.create_or_update_address(crm_lead.name)

#         # Create or Update Contact
#         contact = self.create_or_update_contact(crm_lead.name)

#         # Link CRM Lead to Contact and Address
#         self.link_lead_with_contact_and_address(crm_lead.name, contact.name, address.name)

#     def create_or_update_crm_lead(self):
#         lead_exists = frappe.db.exists('Lead', {'lead_name': self.client_name})

#         primary_phone, whatsapp_phone = self.get_contact_phones()

#         if lead_exists:
#             # Update existing lead
#             lead_doc = frappe.get_doc('Lead', {'lead_name': self.owner_name})
#             lead_doc.email_id = self.get_contact_email()
#             if primary_phone:
#                 lead_doc.mobile_no = primary_phone
#             if whatsapp_phone:
#                 lead_doc.whatsapp_no = whatsapp_phone
#             lead_doc.save(ignore_permissions=True)
#             frappe.msgprint(f'Lead {lead_doc.name} updated successfully!')
#         else:
#             # Create new lead
#             lead_doc = frappe.get_doc({
#                 'doctype': 'Lead',
#                 'lead_name': self.owner_name,
#                 'company_name': self.business_name,
#                 'email_id': self.get_contact_email(),
#                 'mobile_no': primary_phone,
#                 'whatsapp_no': whatsapp_phone,
#                 'status': 'Lead',
#                 'lead_owner': self.owner
#             })
#             lead_doc.insert(ignore_permissions=True)
#             frappe.msgprint(f'Lead {lead_doc.name} created successfully!')

#         return lead_doc

# def create_or_update_address(self, lead_name):
#     address_exists = frappe.db.exists('Address', {
#         'address_title': self.client_name,
#         'address_type': 'Office'
#     })

#     if address_exists:
#         # Update existing address
#         address_doc = frappe.get_doc('Address', {
#             'address_title': self.client_name,
#             'address_type': 'Office'
#         })
#         address_doc.address_line1 = self.address
#         address_doc.city = self.city
#         address_doc.state = self.state
#         address_doc.country = self.country
#         address_doc.email_id = self.get_contact_email()
#         address_doc.phone = self.get_primary_phone()
#         address_doc.save(ignore_permissions=True)
#         frappe.msgprint(f'Address {address_doc.name} updated successfully!')
#     else:
#         # Create new address
#         address_doc = frappe.get_doc({
#             'doctype': 'Address',
#             'address_title': self.client_name,
#             'address_type': 'Office',
#             'address_line1': self.address,
#             'city': self.city,
#             'state': self.state,
#             'country': self.country,
#             'email_id': self.get_contact_email(),
#             'phone': self.get_primary_phone(),
#             'links': [{
#                 'link_doctype': 'Lead',
#                 'link_name': lead_name
#             }]
#         })
#         address_doc.insert(ignore_permissions=True)
#         frappe.msgprint(f'Address {address_doc.name} created successfully!')

#     return address_doc

# def create_or_update_contact(self, lead_name):
#     contact_exists = frappe.db.exists('Contact', {
#         'first_name': self.get_first_name(),
#         'last_name': self.get_last_name()
#     })

#     if contact_exists:
#         # Update existing contact
#         contact_doc = frappe.get_doc('Contact', {
#             'first_name': self.get_first_name(),
#             'last_name': self.get_last_name()
#         })
#         contact_doc.email_id = self.get_contact_email()
#         contact_doc.phone = self.get_primary_phone()
#         contact_doc.company_name = self.client_name
#         contact_doc.designation = self.get_designation()
#         contact_doc.save(ignore_permissions=True)
#         frappe.msgprint(f'Contact {contact_doc.name} updated successfully!')
#     else:
#         # Create new contact
#         contact_doc = frappe.get_doc({
#             'doctype': 'Contact',
#             'first_name': self.get_first_name(),
#             'last_name': self.get_last_name(),
#             'email_id': self.get_contact_email(),
#             'phone': self.get_primary_phone(),
#             'company_name': self.client_name,
#             'designation': self.get_designation(),
#             'links': [{
#                 'link_doctype': 'Lead',
#                 'link_name': lead_name
#             }]
#         })
#         contact_doc.insert(ignore_permissions=True)
#         frappe.msgprint(f'Contact {contact_doc.name} created successfully!')

#     return contact_doc

# def link_lead_with_contact_and_address(self, lead_name, contact_name, address_name):
#     # Link CRM Lead with Contact and Address
#     if not frappe.db.exists('Dynamic Link', {'parent': lead_name, 'link_name': contact_name, 'link_doctype': 'Contact'}):
#         frappe.get_doc({
#             'doctype': 'Dynamic Link',
#             'parenttype': 'Lead',
#             'parent': lead_name,
#             'link_doctype': 'Contact',
#             'link_name': contact_name
#         }).insert(ignore_permissions=True)

#     if not frappe.db.exists('Dynamic Link', {'parent': lead_name, 'link_name': address_name, 'link_doctype': 'Address'}):
#         frappe.get_doc({
#             'doctype': 'Dynamic Link',
#             'parenttype': 'Lead',
#             'parent': lead_name,
#             'link_doctype': 'Address',
#             'link_name': address_name
#         }).insert(ignore_permissions=True)

# def remove_links(self, lead_name):
#     # Remove all links associated with the lead
#     links = frappe.get_all('Dynamic Link', filters={'parent': lead_name})
#     for link in links:
#         frappe.delete_doc('Dynamic Link', link.name, ignore_permissions=True)
#     frappe.msgprint(f'All links for Lead {lead_name} removed successfully!')

# def get_contact_email(self):
#     if self.contact_email:
#         for contact in self.contact_email:
#             if contact.is_primary:
#                 return contact.email
#     return None

# def get_contact_phones(self):
#     primary_phone = None
#     whatsapp_phone = None
#     if self.contact_phones:  # Using contact_phones
#         for contact in self.contact_phones:
#             if contact.is_primary_mobile_no:
#                 primary_phone = contact.phone
#             if contact.custom_is_whatsapp:
#                 whatsapp_phone = contact.phone
#     return primary_phone, whatsapp_phone

# def get_primary_phone(self):
#     # Assuming primary phone is the one marked as is_primary_mobile_no
#     return self.get_contact_phones()[0]

# def get_first_name(self):
#     if self.contact_details:
#         return self.contact_details[0].contact_person.split()[0]
#     return None

# def get_last_name(self):
#     if self.contact_details:
#         return self.contact_details[0].contact_person.split()[-1]
#     return None

# def get_designation(self):
#     if self.contact_details:
#         return self.contact_details[0].designation
#     return None
