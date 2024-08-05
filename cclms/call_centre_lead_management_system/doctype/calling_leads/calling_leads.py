# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class CallingLeads(Document):
    pass
#     def after_insert(self):
#         # After inserting a new calling lead, create address and contact
#         self.create_address()
#         self.create_contact()

#     def create_address(self):
#         # Create an address based on calling leads data
#         address_doc = frappe.new_doc("Address")
#         address_doc.update({
#             "address_title": self.business_name,
#             "address_line1": self.address,
#             "address_line2": self.address,
#             "city": self.city,
#             "state": self.state,
#             "pincode": self.zippostal_code,
#             "country": self.country,
#             "links": [{
#                 "link_doctype": "Calling Leads",
#                 "link_name": self.name
#             }]
#         })

#         try:
#             address_doc.insert(ignore_permissions=True)
#         except Exception as e:
#             frappe.log_error(f"Error creating address: {e}", _("Create Address Error"))

#     def create_contact(self):
#         # Create a contact based on calling leads data
#         contact_doc = frappe.new_doc("Contact")
#         contact_doc.update({
#             "first_name": self.owner_name,
#             "email_ids": [{
#                 "email_id": email.email_id,
#                 "is_primary": 1 if idx == 0 else 0
#             } for idx, email in enumerate(self.email_address)],
#             "phone_nos": [{
#                 "phone": phone.phone,
#                 "is_primary_phone": 1 if idx == 0 else 0,
#                 "is_primary_mobile_no": 0
#             } for idx, phone in enumerate(self.phone_number)],
#             "links": [{
#                 "link_doctype": "Calling Leads",
#                 "link_name": self.name
#             }]
#         })

#         try:
#             contact_doc.insert(ignore_permissions=True)
#         except Exception as e:
#             frappe.log_error(f"Error creating contact: {e}", _("Create Contact Error"))
# class CallingLeads(Document):
# 	def create_address_and_contact(doc, method):
# 			# Create Address record
# 			address = frappe.get_doc({
# 				"doctype": "Address",
# 				"address_title": doc.business_name,
# 				"address_line1": doc.state,
# 				"address_line2": doc.city,
# 				"city": doc.city,
# 				"state": doc.state,
# 				"pincode": doc.zippostal_code,
# 				"country": doc.country,
# 				"links": [{
# 					"link_doctype": "Calling Leads",
# 					"link_name": doc.name
# 				}]
# 			})
# 			address.insert(ignore_permissions=True)

# 			# Create Contact record
# 			contact = frappe.get_doc({
# 				"doctype": "Contact",
# 				"first_name": doc.owner_name,
# 				"email_ids": [{
# 					"email_id": email.email_id,
# 					"is_primary": 1 if idx == 0 else 0
# 				} for idx, email in enumerate(doc.email_address)],
# 				"phone_nos": [{
# 					"phone": phone.phone,
# 					"is_primary_phone": 1 if idx == 0 else 0,
# 					"is_primary_mobile_no": 0
# 				} for idx, phone in enumerate(doc.phone_number)],
# 				"links": [{
# 					"link_doctype": "Calling Leads",
# 					"link_name": doc.name
# 				}]
# 			})
# 			contact.insert(ignore_permissions=True)
# class CallingLeads(Document):
# 	def create_address_and_contact(doc, method):
#     # Create Address record
#     address = frappe.get_doc({
# 			"doctype": "Address",
# 			"address_title": doc.business_name,
# 			"address_line1": doc.state,
# 			"address_line2": doc.city,
# 			"city": doc.city,
# 			"state": doc.state,
# 			"pincode": doc.zippostal_code,
# 			"country": doc.country,
# 			"links": [{
# 			"link_doctype": "Calling Leads",
# 			"link_name": doc.name
# 			}]
# 		})
# 	    address.insert(ignore_permissions=True)
#     # Create Contact record
# 		contact = frappe.get_doc({
# 			"doctype": "Contact",
# 			"first_name": doc.owner_name,
# 			"email_ids": [{
# 			"email_id": email.email_id,
# 			"is_primary": 1 if idx == 0 else 0
# 			} for idx, email in enumerate(doc.email_address)],
# 			"phone_nos": [{
# 			"phone": phone.phone,
# 			"is_primary_phone": 1 if idx == 0 else 0,
# 			"is_primary_mobile_no": 0
# 			} for idx, phone in enumerate(doc.phone_number)],
# 			"links": [{
# 			"link_doctype": "Calling Leads",
# 			"link_name": doc.name
# 			}]
# 		})
# 		contact.insert(ignore_permissions=True)
