import frappe
from frappe.model.document import Document
from frappe.permissions import add_user_permission, remove_user_permission
from frappe.utils import now
from frappe.utils.password import update_password, set_encrypted_password
import secrets
import string

PASSWORD_MANAGER_ROLES = {"System Manager", "HR Manager", "Sales Manager"}

# Force same Role Profile + Module Profile on every Sales Agent user
DEFAULT_ROLE_PROFILE = "Sales Executive"
DEFAULT_MODULE_PROFILE = "Sales Executive"


class SalesAgent(Document):
    def validate(self):
        # normalize email + full name
        if self.email:
            self.email = (self.email or "").strip().lower()

        self.full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()

        # always keep link to User by email
        if self.email:
            self.user = self.email

    def after_insert(self):
        self.sync_all(old=None)

    def on_update(self):
        old = self.get_doc_before_save()
        self.sync_all(old=old)

    def on_trash(self):
        # remove permissions using current values
        self.refresh_user_permissions(old=self, remove_only=True)

    # -----------------------------
    # Main Orchestrator
    # -----------------------------
    def sync_all(self, old=None):
        # guard against recursion
        if getattr(frappe.flags, "sales_agent_sync_in_progress", False):
            return

        frappe.flags.sales_agent_sync_in_progress = True
        try:
            # 1) handle email rename (User.name is email)
            self.handle_email_change(old)

            # 2) ensure User exists (reuse if exists)
            self.ensure_user()

            # 3) ensure Employee exists & linked (always)
            self.ensure_employee()

            # 4) sync latest data into User/Employee
            self.sync_user()
            self.sync_employee()

            # 5) apply enable/disable policy
            self.apply_active_status()

            # 6) refresh user permissions (remove old → add new)
            self.refresh_user_permissions(old=old)

        finally:
            frappe.flags.sales_agent_sync_in_progress = False

    # -----------------------------
    # Enable / Disable Policy
    # -----------------------------
    def is_inactive(self) -> bool:
        # enable=1 => active, enable=0 => inactive
        return not bool(self.enable)

    def apply_active_status(self):
        inactive = self.is_inactive()

        # USER.enabled (enable disabled user when enable=1)
        if self.email and frappe.db.exists("User", self.email):
            frappe.db.set_value("User", self.email, "enabled", 0 if inactive else 1)

        # EMPLOYEE.status
        if self.employee and frappe.db.exists("Employee", self.employee):
            frappe.db.set_value(
                "Employee", self.employee, "status", "Left" if inactive else "Active"
            )

    # -----------------------------
    # EMAIL CHANGE HANDLING
    # -----------------------------
    def handle_email_change(self, old):
        if not old:
            return

        old_email = (old.email or "").strip().lower()
        new_email = (self.email or "").strip().lower()

        if not old_email or not new_email or old_email == new_email:
            return

        # if new email already exists, cannot rename into it
        if frappe.db.exists("User", new_email):
            frappe.throw(f"Cannot change email. User already exists: {new_email}")

        # rename User document if old exists
        if frappe.db.exists("User", old_email):
            frappe.rename_doc("User", old_email, new_email, force=True)

        # update linked employee.user_id
        if self.employee and frappe.db.exists("Employee", self.employee):
            frappe.db.set_value("Employee", self.employee, "user_id", new_email)

        # keep Sales Agent.user link correct
        self.user = new_email

    # -----------------------------
    # USER Create/Reuse + Password on Create
    # -----------------------------
    def ensure_user(self):
        if not self.email:
            frappe.throw("Email is required to create/reuse a User.")

        self.user = self.email  # keep link

        if frappe.db.exists("User", self.email):
            # reuse existing user
            return

        # create new user
        user = frappe.get_doc({
            "doctype": "User",
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "gender": self.gender,
            "send_welcome_email": 0,  # we are setting password manually
            "enabled": 1 if self.enable else 0,
        })

        # Force same Role Profile + Module Profile
        user.role_profile_name = DEFAULT_ROLE_PROFILE
        user.module_profile = DEFAULT_MODULE_PROFILE

        user.insert(ignore_permissions=True)

        # set random password on first creation (store in Sales Agent)
        self._set_and_store_new_password(self.email, length=12, bypass_role_check=False)

    def sync_user(self):
        if not self.email or not frappe.db.exists("User", self.email):
            return

        user = frappe.get_doc("User", self.email)
        user.first_name = self.first_name
        user.last_name = self.last_name
        user.gender = self.gender

        # Force same Role Profile + Module Profile
        user.role_profile_name = DEFAULT_ROLE_PROFILE
        user.module_profile = DEFAULT_MODULE_PROFILE

        user.save(ignore_permissions=True)

    # -----------------------------
    # EMPLOYEE Create/Link (Always)
    # -----------------------------
    def ensure_employee(self):
        # if already linked and exists, ok
        if self.employee and frappe.db.exists("Employee", self.employee):
            return

        # find existing employee by user_id OR by pseudo name
        emp_name = (
            frappe.db.get_value("Employee", {"user_id": self.email}, "name")
            or frappe.db.get_value("Employee", {"custom_pseudo_name": self.agent_name}, "name")
        )

        if emp_name:
            frappe.db.set_value("Sales Agent", self.name, "employee", emp_name)
            self.employee = emp_name
            return

        # create new employee
        employee = frappe.get_doc({
            "doctype": "Employee",
            "custom_pseudo_name": self.agent_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "employee_name": self.full_name,
            "user_id": self.email,
            "company": self.company,
            "gender": self.gender,
            "date_of_birth": self.date_off_berth,
            "date_of_joining": self.join_date,
            "cell_number": self.phone,
            "designation": self.designation,
            "department": self.department,
            "custom_employee_id": self.id,
            "custom_father_name": getattr(self, "father_name", None),
            "current_address": self.address,
            "passport_number": getattr(self, "nic", None),
            "branch": self.branch
        })
        employee.insert(ignore_permissions=True)

        frappe.db.set_value("Sales Agent", self.name, "employee", employee.name)
        self.employee = employee.name

    def sync_employee(self):
        if not self.employee or not frappe.db.exists("Employee", self.employee):
            return

        employee = frappe.get_doc("Employee", self.employee)
        employee.custom_pseudo_name = self.agent_name
        employee.first_name = self.first_name
        employee.last_name = self.last_name
        employee.employee_name = self.full_name
        employee.company = self.company
        employee.user_id = self.email
        employee.gender = self.gender
        employee.date_of_birth = self.date_off_berth
        employee.date_of_joining = self.join_date
        employee.cell_number = self.phone
        employee.designation = self.designation
        employee.department = self.department
        employee.custom_employee_id = self.id
        employee.custom_father_name = getattr(self, "father_name", None)
        employee.current_address = self.address
        employee.passport_number = getattr(self, "nic", None)
        employee.branch = self.branch
        employee.save(ignore_permissions=True)

    # -----------------------------
    # Password helpers + Button APIs
    # -----------------------------


    def _has_password_manager_role(self) -> bool:
        user_roles = set(frappe.get_roles(frappe.session.user))
        return bool(user_roles.intersection(PASSWORD_MANAGER_ROLES))

    def _generate_password(self, length: int = 12) -> str:
        length = int(length) if length else 12
        length = max(8, min(length, 64))

        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _set_and_store_new_password(
        self,
        user_email: str,
        length: int = 12,
        bypass_role_check: bool = False,
    ) -> str:
        if not bypass_role_check and not self._has_password_manager_role():
            frappe.throw("Only System Manager / HR Manager / Sales Manager can generate or view passwords.")

        new_pass = self._generate_password(length)

        # set login password on User
        update_password(user_email, new_pass)

        # store encrypted password in Sales Agent Password field (v15 safe way)
        set_encrypted_password(self.doctype, self.name, "agent_password", new_pass)

        # update timestamp
        self.db_set("last_password_set_on", now(), update_modified=False)

        return new_pass


    @frappe.whitelist()
    def generate_new_password(self, length: int = 12):
        if not self.email or not frappe.db.exists("User", self.email):
            frappe.throw("User does not exist. Save Sales Agent first to create User.")

        return self._set_and_store_new_password(self.email, length=length, bypass_role_check=False)

    @frappe.whitelist()
    def get_saved_password(self):
        if not self._has_password_manager_role():
            frappe.throw("Only System Manager / HR Manager / Sales Manager can generate or view passwords.")

        return self.get_password("agent_password")

    # -----------------------------
    # User Permissions (self docs only)
    # -----------------------------
    def refresh_user_permissions(self, old=None, remove_only=False):
        # remove permissions using OLD values
        self._remove_permissions_for_doc(old or self)

        if remove_only:
            return

        # add current permissions
        self._add_permissions_for_doc(self)

    def _add_permissions_for_doc(self, doc):
        if not doc.email:
            return

        add_user_permission("Sales Agent", doc.name, doc.email)

        if doc.employee:
            add_user_permission("Employee", doc.employee, doc.email)
        if doc.company:
            add_user_permission("Company", doc.company, doc.email)
        if doc.branch:
            add_user_permission("Branch", doc.branch, doc.email)

    def _remove_permissions_for_doc(self, doc):
        if not doc or not doc.email:
            return

        remove_user_permission("Sales Agent", doc.name, doc.email)

        if doc.employee:
            remove_user_permission("Employee", doc.employee, doc.email)
        if doc.company:
            remove_user_permission("Company", doc.company, doc.email)
        if doc.branch:
            remove_user_permission("Branch", doc.branch, doc.email)
