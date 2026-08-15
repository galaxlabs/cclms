import frappe


SALES_AGENT_FIELDS = [
    "name",
    "full_name",
    "agent_name",
    "email",
    "user",
    "branch",
    "company",
    "employee",
    "designation",
    "department",
    "phone",
    "enable",
]

SYSTEM_ROLES = {"All", "Guest"}
STAFF_ROLES = {"Admin", "System Manager", "Administrator", "Sales Manager"}
PORTAL_ROLES = {"Sales Agent", "Sales User", "Data Executive", "Onboarding Executive", "OC", "Sales Manager"}


def _user_info(user):
    info = frappe.db.get_value(
        "User",
        user,
        ["name", "email", "full_name", "first_name", "last_name", "enabled"],
        as_dict=True,
    ) or {}
    return {
        "name": info.get("name") or user,
        "email": info.get("email") or user,
        "full_name": info.get("full_name") or info.get("first_name") or user,
        "first_name": info.get("first_name"),
        "last_name": info.get("last_name"),
        "enabled": info.get("enabled"),
    }


def _get_sales_agent(name):
    if not name:
        return None
    return frappe.db.get_value("Sales Agent", name, SALES_AGENT_FIELDS, as_dict=True)


def _find_sales_agent(user, email):
    """Resolve the Sales Agent linked to a user, mirroring the SANHA pattern:
    User Permission -> Sales Agent, then email, then owner fallback."""
    if not frappe.db.exists("DocType", "Sales Agent"):
        return None

    permission_rows = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Sales Agent"},
        fields=["for_value", "is_default"],
        order_by="is_default desc, modified desc",
        limit=5,
        ignore_permissions=True,
    )
    for row in permission_rows:
        agent = _get_sales_agent(row.get("for_value"))
        if agent:
            return agent

    if email:
        agent_name = frappe.db.get_value("Sales Agent", {"email": email}, "name")
        agent = _get_sales_agent(agent_name)
        if agent:
            return agent

    agent_name = frappe.db.get_value("Sales Agent", {"user": user}, "name")
    return _get_sales_agent(agent_name)


@frappe.whitelist(allow_guest=True)
def get_current_sales_agent():
    """SPA-safe auth state for the CRM Portal (xg-system / XG Hub) sales agents.

    Server-side lookups only — no need for the SPA to read User / User Permission /
    Sales Agent through REST. Mirrors the SANHA get_current_user pattern.
    """
    user = frappe.session.user
    if not user or user == "Guest":
        return {
            "is_authenticated": False,
            "message": "Guest",
            "user": None,
            "name": "Guest",
            "email": None,
            "full_name": "Guest",
            "roles": [],
            "salesAgentName": None,
            "salesAgent": None,
        }

    info = _user_info(user)
    roles = [role for role in frappe.get_roles(user) if role not in SYSTEM_ROLES]
    agent = None

    is_admin = bool(STAFF_ROLES.intersection(roles))
    if not is_admin:
        agent = _find_sales_agent(user, info.get("email"))
        if agent and not any(role in PORTAL_ROLES for role in roles):
            roles.append("Sales Agent")

    agent_name = agent.get("name") if agent else None
    return {
        "is_authenticated": True,
        "message": user,
        "user": user,
        "name": user,
        "email": info.get("email"),
        "full_name": info.get("full_name"),
        "roles": roles,
        "is_manager": is_admin or "Sales Manager" in roles,
        "salesAgentName": agent_name,
        "salesAgent": agent,
        "branch": agent.get("branch") if agent else None,
        "company": agent.get("company") if agent else None,
        "employee": agent.get("employee") if agent else None,
    }


@frappe.whitelist(allow_guest=True)
def get_current_user():
    """Alias matching the SANHA pattern for generic SPA consumers."""
    return get_current_sales_agent()


@frappe.whitelist(allow_guest=True)
def get_me():
    return get_current_sales_agent()
