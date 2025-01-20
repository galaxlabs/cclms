# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.utils import date_diff, nowdate
from frappe.model.document import Document
from frappe.utils import today, add_days

class ATMLeads(Document):
    def validate(self):
        self.validate_lead_state()

    # def before_save(self):
    #     self.update_dates_and_days()

    def validate_lead_state(self):
        if not self.company:
            frappe.throw(
                _("Please select a company before saving the lead."),
                title=_("Company Not Selected")
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
    
    # def update_dates_and_days(self):
    #     """
    #     Update specific date fields based on workflow state only when the state changes.
    #     Maintain the original date unless manually edited.
    #     """
    #     current_date = nowdate()
    #     should_save = False

    #     # Workflow state to date field mapping
    #     workflow_dates = {
    #         "Approved": "approve_date",
    #         "Agreement Sent": "agreement_sent_date",
    #         "Signed": "sign_date",
    #         "Converted": "convert_date",
    #         "Installed": "install_date",
    #         "Removed": "remove_date"
    #     }

    #     # Set dates only if the state changes and the corresponding field is empty
    #     for state, date_field in workflow_dates.items():
    #         if self.workflow_state == state and not self.get(date_field):
    #             self.db_set(date_field, current_date)
    #             should_save = True

    #     # Call the function to calculate day differences
    #     self.calculate_days()

    #     # Commit only if a field is updated
    #     if should_save:
    #         frappe.db.commit()
    #         frappe.msgprint(_("Dates and days updated based on workflow state."))

    # def calculate_days(self):
    #     """
    #     Calculate the difference in days between specific date fields.
    #     """
    #     def calculate_days_diff(start_field, end_field, days_field):
    #         if self.get(start_field):
    #             end_date = self.get(end_field) or nowdate()
    #             days = date_diff(end_date, self.get(start_field))
    #             self.db_set(days_field, days)

    #     # Sequence of fields for day calculations
    #     date_pairs = [
    #         ("approve_date", "agreement_sent_date", "approved_days"),
    #         ("agreement_sent_date", "sign_date", "agreement_sent_days"),
    #         ("sign_date", "convert_date", "sign_days"),
    #         ("convert_date", "install_date", "convert_days"),
    #         ("install_date", "remove_date", "install_days"),
    #     ]

    #     for start_field, end_field, days_field in date_pairs:
    #         calculate_days_diff(start_field, end_field, days_field)

    #     # Calculate days since removal if `remove_date` exists
    #     if self.get("remove_date"):
    #         self.db_set("remove_days", date_diff(nowdate(), self.get("remove_date")))

    # def update_dates_and_days(self):
    #     current_date = nowdate()
    #     should_save = False

    #     workflow_dates = {
    #         "Approved": "approve_date",
    #         "Agreement Sent": "agreement_sent_date",
    #         "Signed": "sign_date",
    #         "Converted": "convert_date",
    #         "Installed": "install_date",
    #         "Removed": "remove_date"
    #     }

    #     for state, date_field in workflow_dates.items():
    #         if self.workflow_state == state and not getattr(self, date_field):
    #             self.db_set(date_field, current_date)
    #             should_save = True

    #     # Calculate days between dates
    #     self.calculate_days()

    #     # Commit if any field was updated
    #     if should_save:
    #         frappe.db.commit()
    #         frappe.msgprint(_("Dates and days updated based on workflow state."))

    # def calculate_days(self):
    #     def calculate_days_diff(start_field, end_field, days_field):
    #         if getattr(self, start_field):
    #             end_date = getattr(self, end_field) or nowdate()
    #             days = date_diff(end_date, getattr(self, start_field))
    #             self.db_set(days_field, days)

    #     calculate_days_diff('approve_date', 'agreement_sent_date', 'approved_days')
    #     calculate_days_diff('agreement_sent_date', 'sign_date', 'agreement_sent_days')
    #     calculate_days_diff('sign_date', 'convert_date', 'sign_days')
    #     calculate_days_diff('convert_date', 'install_date', 'convert_days')
    #     calculate_days_diff('install_date', 'remove_date', 'install_days')

    #     if self.remove_date:
    #         self.db_set('remove_days', date_diff(nowdate(), self.remove_date))
    
        

    # def notify_on_workflow_change(doc, method):
    #     previous_doc = doc.get_doc_before_save()
    #     # Check if the workflow state has changed
    #     if doc.workflow_state != doc.get_doc_before_save().workflow_state:
    #         # Define notification message based on the new workflow state
    #         message = ""
    #         if doc.workflow_state == "Approved":
    #             message = f"The lead {doc.name} for {doc.business_name} at {doc.address} has been approved."
    #         elif doc.workflow_state == "Rejected":
    #             message = f"The lead {doc.name} for {doc.business_name} at {doc.address} has been rejected."
    #         elif doc.workflow_state == "Pending":
    #             message = f"The lead {doc.name} for {doc.business_name} at {doc.address} is pending review."
    #         elif doc.workflow_state == "Signed":
    #             message = f"The lead {doc.name} for {doc.business_name} at {doc.address} has been signed."

    #         # Only proceed if a relevant message is generated
    #         if message:
    #             # Create a notification in the Notification Log for all users with relevant permissions
    #             recipients = frappe.get_all("User", filters={"enabled": 1}, pluck="name")
    #             for user in recipients:
    #                 frappe.get_doc({
    #                     "doctype": "Notification Log",
    #                     "subject": f"Workflow Update - {doc.workflow_state}",
    #                     "email_content": message,
    #                     "for_user": user,
    #                     "document_type": doc.doctype,
    #                     "document_name": doc.name
    #                 }).insert(ignore_permissions=True)

    # # Call the function on workflow state change
    # notify_on_workflow_change(doc, method)

    # Assuming you have a list of ATM lead documents

# import frappe
# from frappe import _
# from frappe.utils import now
# from frappe.utils import date_diff, nowdate
# from frappe.model.document import Document
# from frappe.utils import date_diff, today


# class ATMLeads(Document):
#     def validate(self):
#         self.validate_lead_state()

#     def before_save(self):
#         self.update_dates_and_days()
        
#             def validate_lead_state(self):
#         # Check if the company is selected

#         if not self.company:
#             frappe.throw(
#                 _("Please select a company before saving the lead."),
#                 title=_("Company Not Selected")
#             )

#         # Fetch the operator company details
#         company = frappe.get_doc('Operator Companies', self.company)

#         # Ensure the company exists
#         if not company:
#             frappe.throw(
#                 _("The selected company does not exist."),
#                 title=_("Invalid Company")
#             )

#         # Access the permitted states from the child table
#         permitted_states = company.state_name  # This is the child table containing permitted states

#         if permitted_states:
#             # Check if the lead's state_code is in the permitted states
#             state_permitted = any(
#                 state.state_code == self.state_code
#                 for state in permitted_states
#             )
#             if not state_permitted:
#                 frappe.throw(
#                     _("The selected state ({0}) is not allowed for the company {1}. Please select a valid state.").format(self.state_code, self.company),
#                     title=_("State Not Allowed")
#                 )
#         else:
#             # If the child table is empty, allow all states
#             frappe.msgprint(
#                 _("No restricted states specified for the selected company. All states are allowed."),
#                 alert=True
#             )

#     def on_update(self):
#     # Ensure 'item_created' attribute exists
#         if not hasattr(self, 'item_created'):
#             self.item_created = 0
#             self.db_set('item_created', 0)  # Set default value in the database

#         # Check if the workflow state is "Signed" and if item has not been created
#         if self.workflow_state == "Signed" and not self.item_created:
#             # Step 1: Create Item
#             item_code = f"{self.address}"
#             item_name = f"{self.business_name}"
#             item_description = f"{self.address} - {self.business_name} - {self.business_type}"
#             item_group = self.business_type

#             new_item = frappe.get_doc({
#                 "doctype": "Item",
#                 "item_code": item_code,
#                 "item_name": item_name,
#                 "description": item_description,
#                 "item_group": item_group,
#                 "is_stock_item": 0,
#                 "default_supplier": self.company
#             })
#             new_item.insert()
#             frappe.db.commit()

#             # Mark item as created
#             frappe.msgprint(f"Item '{item_name}' has been successfully created.")

#             # Step 2: Create Supplier
#             supplier_name = f"{self.owner_name} - {self.business_name}"
#             new_supplier = frappe.get_doc({
#                 "doctype": "Supplier",
#                 "supplier_name": supplier_name,
#                 "supplier_type": "Company",  # Adjust type as per your need
#                 "contact_info": {
#                     "email_id": self.email_address,
#                     "phone": self.phone_number
#                 },
#                 "supplier_group": "All Suppliers"  # Set as required
#             })
#             new_supplier.insert()
#             frappe.db.commit()
#             frappe.msgprint(f"Supplier '{supplier_name}' has been successfully created.")

#             # Step 3: Create Sales Order
#             sales_order = frappe.get_doc({
#                 "doctype": "Sales Order",
#                 "customer": self.company,  # Selects the company as the customer
#                 "delivery_date": frappe.utils.add_days(frappe.utils.today(), 7),  # Example: delivery in 7 days
#                 "items": [
#                     {
#                         "item_code": item_code,
#                         "qty": 1,  # Adjust as needed
#                         "rate": self.base_rent  # Using base rent as the rate
#                     }
#                 ]
#             })
#             sales_order.insert()
#             frappe.db.commit()
#             frappe.msgprint(f"Sales Order for '{self.company}' has been successfully created.")
            
#         else:
#             frappe.msgprint("This item, supplier, and sales order have already been created.")

#     def on_update(self):
#         # Check if the workflow state is "Approved"
#         if self.workflow_state == "Approved":
#             # Notification message
#             message = f"The lead '{self.name}' for business '{self.business_name}' at address '{self.address}' has been approved."
            
#             # Get related users (e.g., based on lead owner or executive)
#             recipients = get_recipients(self)

#             # Send real-time message to each recipient
#             for user in recipients:
#                 frappe.publish_realtime(
#                     event="msgprint",
#                     message=message,
#                     user=user,
#                     title="Workflow Update"
#                 )

#     def get_recipients(self):
#         # Example function to get list of recipients
#         recipients = []
#         if self.owner:
#             recipients.append(self.owner)
#         if self.executive:
#             recipients.append(self.executive)
#         return recipients

    
#     def before_save(self):
#     # Update dates and days calculations based on workflow state
#         update_dates_and_days(self)

#     def update_dates_and_days(self):
#         current_date = nowdate()
#         should_save = False

#         # Update dates if workflow state changes and date fields are blank
#         workflow_dates = {
#             "Approved": "approve_date",
#             "Agreement Sent": "agreement_sent_date",
#             "Signed": "sign_date",
#             "Converted": "convert_date",
#             "Installed": "install_date",
#             "Removed": "remove_date"
#         }

#         for state, date_field in workflow_dates.items():
#             if self.workflow_state == state and not getattr(self, date_field):
#                 self.db_set(date_field, self.modified)  # Use the document's last modified date
#                 should_save = True

#         # Calculate days between dates
#         calculate_days(self)

#         # Commit if any field was backdated
#         if should_save:
#             frappe.db.commit()
#             frappe.msgprint("Fields updated and saved automatically.")

#     def calculate_days(self):
#         # Helper function to calculate days difference between dates
#         def calculate_days_diff(start_field, end_field, days_field):
#             if getattr(self, start_field):
#                 end_date = getattr(self, end_field) or nowdate()
#                 days = date_diff(end_date, getattr(self, start_field))
#                 self.db_set(days_field, days)

#         # Calculate differences for each field
#         calculate_days_diff('approve_date', 'agreement_sent_date', 'approved_days')
#         calculate_days_diff('agreement_sent_date', 'sign_date', 'agreement_sent_days')
#         calculate_days_diff('sign_date', 'convert_date', 'sign_days')
#         calculate_days_diff('convert_date', 'install_date', 'convert_days')
#         calculate_days_diff('install_date', 'remove_date', 'install_days')

#         if self.remove_date:
#             self.db_set('remove_days', date_diff(nowdate(), self.remove_date))
    
    
    # def on_update(self):
    # # Check if status is "Signed" and if item has not already been created
    #     if self.workflow_state == "Signed" and not getattr(self, "item_created", False):
    # # Code to create the item or take appropriate action

    #         # Set item details from lead data
    #         item_code = f"{self.address}"
    #         item_name = f"{self.business_name}"
    #         item_description = f"{self.address} - {self.business_name} - {self.business_type}"
    #         item_group = self.business_type
    #         custom_operations_hours = self.hours

    #         # Create Item document
    #         new_item = frappe.get_doc({
    #             "doctype": "Item",
    #             "item_code": item_code,
    #             "item_name": item_name,
    #             "description": item_description,
    #             "item_group": item_group,
    #             "is_stock_item": 0,
    #             "default_supplier": self.company
    #         })

    #         # Insert item into database
    #         new_item.insert()
    #         frappe.db.commit()

    #         # Mark item as created to avoid duplicates
    #         self.db_set('item_created', 1)  # Sets item_created field to true
    #         frappe.msgprint(f"Item '{item_name}' has been successfully created.")


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
