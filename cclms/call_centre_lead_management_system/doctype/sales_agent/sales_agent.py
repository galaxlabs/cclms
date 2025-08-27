import frappe
from frappe.model.document import Document
from frappe.permissions import add_user_permission, remove_user_permission


class SalesAgent(Document):
	def after_insert(self):
		self.create_self_user_and_employee()
		self.assign_user_permissions()

	def on_update(self):
		self.sync_user()
		self.sync_employee()
		self.assign_user_permissions()

	def on_trash(self):
		# Remove permissions when Sales Agent is deleted
		if self.email:
			remove_user_permission("Sales Agent", self.name, self.email)
			if self.employee:
				remove_user_permission("Employee", self.employee, self.email)
			if self.company:
				remove_user_permission("Company", self.company, self.email)
			if self.branch:
				remove_user_permission("Branch", self.branch, self.email)
			frappe.msgprint("User permissions removed for deleted Sales Agent.")

	def create_self_user_and_employee(self):
		if not self.email:
			frappe.throw("Email is required to create a user.")

		# --- Create User ---
		user = frappe.get_doc("User", self.email) if frappe.db.exists("User", self.email) else None

		if not user:
			user = frappe.get_doc({
				"doctype": "User",
				"email": self.email,
				"first_name": self.first_name,
				"last_name": self.last_name,
				"gender": self.gender,
				"send_welcome_email": 1,
				"enabled": 1
			})
			user.insert(ignore_permissions=True)
			frappe.msgprint(f"✅ User created: {self.email}")
		else:
			frappe.msgprint(f"ℹ️ User already exists: {self.email}")

		# --- Assign Role Profile based on Branch ---
		role_profile = self.get_role_profile_for_branch()
		if role_profile:
			user.role_profile_name = role_profile
			frappe.msgprint(f"Assigned Role Profile: {role_profile}")

		# --- Assign Static Module Profile ---
		user.module_profile = "Sales Executive"
		user.save(ignore_permissions=True)
		frappe.msgprint("Assigned Module Profile: Sales Executive")

		# --- Always Create Employee (fresh site, no Employees exist) ---
		employee = frappe.get_doc({
			"doctype": "Employee",
			"custom_pseudo_name": self.agent_name,
			"first_name": self.first_name,
			"last_name": self.last_name,
			"employee_name": f"{self.first_name or ''} {self.last_name or ''}".strip(),
			"user_id": self.email,
			"company": self.company,
			"gender": self.gender,
			"date_of_birth": self.date_off_berth,
			"date_of_joining": self.join_date,
			"cell_number": self.phone,
			"designation": self.designation,
			"department": self.department,
			"custom_employee_id": self.id,
			"custom_father_name": self.father_name,
			"current_address": self.address,
			"passport_number": self.nic,
			"branch": self.branch
		})
		employee.insert(ignore_permissions=True)
		self.db_set("employee", employee.name)
		frappe.msgprint(f"✅ Employee created and linked: {employee.name}")

	def sync_user(self):
		if not frappe.db.exists("User", self.email):
			frappe.msgprint("⚠️ User does not exist to sync.")
			return

		user = frappe.get_doc("User", self.email)
		user.first_name = self.first_name
		user.last_name = self.last_name
		user.gender = self.gender
		user.role_profile_name = self.get_role_profile_for_branch()
		user.module_profile = "Sales Executive"
		user.save(ignore_permissions=True)
		frappe.msgprint("🔄 User updated with latest Sales Agent data.")

	def sync_employee(self):
		if not self.employee:
			frappe.msgprint("⚠️ No linked employee to update.")
			return

		if not frappe.db.exists("Employee", self.employee):
			frappe.msgprint("⚠️ Linked Employee record not found.")
			return

		employee = frappe.get_doc("Employee", self.employee)
		employee.custom_pseudo_name = self.agent_name
		employee.employee_name = f"{self.first_name or ''} {self.last_name or ''}".strip()
		employee.company = self.company
		employee.user_id = self.email
		employee.gender = self.gender
		employee.date_of_birth = self.date_off_berth
		employee.date_of_joining = self.join_date
		employee.cell_number = self.phone
		employee.designation = self.designation
		employee.department = self.department
		employee.custom_employee_id = self.id
		employee.custom_father_name = self.father_name
		employee.current_address = self.address
		employee.passport_number = self.nic
		employee.branch = self.branch
		employee.save(ignore_permissions=True)
		frappe.msgprint("🔄 Employee updated with latest Sales Agent data.")

	def assign_user_permissions(self):
		if self.email:
			add_user_permission("Sales Agent", self.name, self.email)
			if self.employee:
				add_user_permission("Employee", self.employee, self.email)
			if self.company:
				add_user_permission("Company", self.company, self.email)
			if self.branch:
				add_user_permission("Branch", self.branch, self.email)
			frappe.msgprint("✅ User permissions set.")

	def get_role_profile_for_branch(self):
		if not self.branch:
			return None

		branch_map = {
			"Karachi": "Karachi Team",
			"Lahore": "Lahore Team",
			"Chandi Garh": "India Team"
		}

		return branch_map.get(self.branch)

# import frappe
# from frappe.model.document import Document
# from frappe.permissions import (
# 	add_user_permission,
# 	get_doc_permissions,
# 	has_permission,
# 	remove_user_permission,
# )
# from frappe.utils import cstr, getdate, today, validate_email_address


# class SalesAgent(Document):
# 	def after_insert(self):
# 		self.create_self_user_and_employee()

# 	def on_update(self):
# 		self.sync_user()
# 		self.sync_employee()

# 	def create_self_user_and_employee(self):
# 		if not self.email:
# 			frappe.throw("Email is required to create a user.")

# 		# --- Create or Get User ---
# 		user = frappe.get_doc("User", self.email) if frappe.db.exists("User", self.email) else None

# 		if not user:
# 			user = frappe.get_doc({
# 				"doctype": "User",
# 				"email": self.email,
# 				"first_name": self.first_name,
# 				"last_name": self.last_name,
# 				"gender": self.gender,
# 				"send_welcome_email": 1,
# 				"enabled": 1
# 			})
# 			user.insert(ignore_permissions=True)
# 			frappe.msgprint(f"User created: {self.email}")
# 		else:
# 			frappe.msgprint(f"User already exists: {self.email}")

# 		# --- Assign Role Profile based on Branch ---
# 		role_profile = self.get_role_profile_for_branch()
# 		if role_profile:
# 			user.role_profile_name = role_profile
# 			frappe.msgprint(f"Assigned Role Profile: {role_profile}")
# 		else:
# 			frappe.msgprint("No matching Role Profile found for the selected branch.")

# 		# --- Assign Static Module Profile ---
# 		user.module_profile = "Sales Executive"
# 		user.save(ignore_permissions=True)
# 		frappe.msgprint("Assigned Module Profile: Sales Executive")

# 		# --- Create Employee if not already linked ---
# 			# --- Create or Link Employee ---
# 		if not self.employee:
# 			# Try to find existing employee by email or full name
# 			existing_employee = frappe.db.get_value("Employee", {"user_id": self.email}) \
# 				or frappe.db.get_value("Employee", {"employee_name": f"{self.first_name or ''} {self.last_name or ''}".strip()})

# 			if existing_employee:
# 				self.db_set("employee", existing_employee)
# 				frappe.msgprint(f"Existing Employee linked: {existing_employee}")
# 			else:
# 				# Create new employee
# 				employee = frappe.get_doc({
# 					"doctype": "Employee",
# 					"custom_pseudo_name": self.agent_name,
# 					"first_name": self.first_name,
# 					"last_name": self.last_name,
# 					"employee_name": f"{self.first_name or ''} {self.last_name or ''}".strip(),
# 					"user_id": self.email,
# 					"company": self.company,
# 					"gender": self.gender,
# 					"date_of_birth": self.date_off_berth,
# 					"date_of_joining": self.join_date,
# 					"cell_number": self.phone,
# 					"designation": self.designation,
# 					"department": self.department,
# 					"custom_employee_id": self.id,
# 					"custom_father_name": self.father_name,
# 					"current_address": self.address,
# 					"passport_number": self.nic,
# 					"branch": self.branch
# 				})
# 				employee.insert(ignore_permissions=True)
# 				self.db_set("employee", employee.name)
# 				frappe.msgprint(f"Employee created and linked: {employee.name}")
# 		else:
# 			frappe.msgprint(f"Sales Agent already linked to Employee: {self.employee}")


# 	def sync_user(self):
# 		if not frappe.db.exists("User", self.email):
# 			frappe.msgprint("User does not exist to sync.")
# 			return

# 		user = frappe.get_doc("User", self.email)
# 		user.first_name = self.first_name
# 		user.last_name = self.last_name
# 		user.gender = self.gender
# 		user.role_profile_name = self.get_role_profile_for_branch()
# 		user.module_profile = "Sales Executive"
# 		user.save(ignore_permissions=True)
# 		frappe.msgprint("User updated with latest Sales Agent data.")

# 	def sync_employee(self):
# 		if not self.employee:
# 			frappe.msgprint("No linked employee to update.")
# 			return

# 		if not frappe.db.exists("Employee", self.employee):
# 			frappe.msgprint("Linked Employee record not found.")
# 			return

# 		employee = frappe.get_doc("Employee", self.employee)
# 		employee.custom_pseudo_name = self.agent_name
# 		employee.employee_name = f"{self.first_name or ''} {self.last_name or ''}".strip()
# 		employee.company = self.company
# 		employee.user_id = self.email
# 		employee.gender = self.gender
# 		employee.date_of_birth = self.date_off_berth
# 		employee.date_of_joining = self.join_date
# 		employee.cell_number = self.phone
# 		employee.designation = self.designation
# 		employee.department = self.department
# 		employee.custom_employee_id = self.id
# 		employee.custom_father_name = self.father_name
# 		employee.current_address = self.address
# 		employee.passport_number = self.nic
# 		employee.branch = self.branch
# 		employee.save(ignore_permissions=True)
# 		frappe.msgprint("Employee updated with latest Sales Agent data.")



# 	def assign_user_permissions(self):
# 		add_user_permission("Sales Agent", self.name, self.email, ignore_permissions=True)
# 		if self.employee:
# 			add_user_permission("Employee", self.employee, self.email, ignore_permissions=True)
# 		if self.company:
# 			add_user_permission("Company", self.company, self.email, ignore_permissions=True)
# 		if self.branch:
# 			add_user_permission("Branch", self.branch, self.email, ignore_permissions=True)
# 		frappe.msgprint("User permissions set.")

# 	def get_role_profile_for_branch(self):
# 		if not self.branch:
# 			return None

# 		branch_map = {
# 			"Karachi": "Karachi Team",
# 			"Lahore": "Lahore Team",
# 			"Chandi Garh": "India Team"
# 		}

# 		return branch_map.get(self.branch)
