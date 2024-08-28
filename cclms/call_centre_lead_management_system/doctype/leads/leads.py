# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Leads(Document):
	pass
	# def on_submit(self):
    # # List of companies and their short names
    # companies = [
    #     {'name': 'Budget Coinz', 'short_name': 'BC'},
    #     {'name': 'Rocket Coin', 'short_name': 'RC'},
    #     {'name': 'Bitcoin Depot', 'short_name': 'BD'},
    #     {'name': 'Bit Stop', 'short_name': 'BS'},
    #     {'name': 'Insta Bit', 'short_name': 'IB'},
    #     {'name': 'Instant Coin Bank', 'short_name': 'ICB'},
    #     {'name': 'Crypto Base', 'short_name': 'CB'},
    #     {'name': 'Coin Works', 'short_name': 'CW'},
    #     {'name': 'Local Coin', 'short_name': 'LC'},
    #     {'name': 'Un Bank', 'short_name': 'UB'}
    # ]


        
    #     for operator in operators:
    #         self.create_operator_lead(operator)
    
    # def create_operator_lead(self, operator):
    #     # Determine the Doctype name for the operator
    #     operator_doctype = operator.replace(" ", "") + "Leads"
        
    #     # Create a new document for the operator
    #     operator_lead = frappe.get_doc({
    #         "doctype": operator_doctype,
    #         "lead_owner": self.lead_owner,
    #         "executive_name": self.executive_name,
    #         "post_date": self.post_date,
    #         "owner_name": self.owner_name,
    #         "business_type": self.business_type,
    #         "business_name": self.business_name,
    #         "business_street_address": self.business_street_address,
    #         "zippostal_code": self.zippostal_code,
    #         "city": self.city,
    #         "country": self.country,
    #         "stateproviance": self.stateproviance,
    #         "email": self.email,
    #         "business_phone_number": self.business_phone_number,
    #         "cell_phone": self.cell_phone,
    #         "whatsapp_no": self.whatsapp_no,
    #         "contract_length": self.contract_length,
    #         "base_rent": self.base_rent,
    #         "hours": self.hours,
    #         "status": "Submitted",  # Setting status as Submitted
    #         "lead_identification": f"{operator[:2]}-{self.post_date}-{frappe.generate_hash(length=8)}",
    #     })
        
    #     # Insert the document
    #     operator_lead.insert(ignore_permissions=True)
        
    # def get_treatry(self, operator):
    #     # Method to get the Treatry for the operator
    #     treatry_doc = frappe.get_doc("Treatry", {"operator": operator, "employee": self.executive_name})
    #     return treatry_doc.name if treatry_doc else None
