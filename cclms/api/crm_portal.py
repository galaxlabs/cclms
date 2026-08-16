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
    "portal_timezone",
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
            "user": "Guest",
            "name": "Guest",
            "email": None,
            "full_name": "Guest",
            "roles": [],
            "is_manager": False,
            "salesAgentName": None,
            "salesAgent": None,
            "branch": None,
            "company": None,
            "employee": None,
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
        "timezone": _get_user_timezone(user),
    }


@frappe.whitelist(allow_guest=True)
def get_current_user():
    """Alias matching the SANHA pattern for generic SPA consumers."""
    return get_current_sales_agent()


@frappe.whitelist(allow_guest=True)
def get_me():
    return get_current_sales_agent()


# ── Theme configuration (backend-driven, shown in Settings → Appearance) ──
# Each theme: id, label, mode (light/dark), primary + secondary color codes,
# sidebar colors, and a background suggestion for the workspace.
PORTAL_THEMES = [
    {
        "id": "default", "label": "Emerald", "mode": "dark",
        "primary": "#10b981", "secondary": "#84cc16",
        "sidebar": "#0f1f18", "sidebar_border": "#1b3328",
        "sidebar_primary": "#84cc16", "sidebar_text": "#0f1f18",
        "workspace": "#0b1410", "card": "#12201a", "surface": "#162620",
        "text": "#eaf5ef", "muted": "#9fb5aa", "border": "#223a30",
    },
    {
        "id": "default", "label": "Emerald Light", "mode": "light",
        "primary": "#0d9488", "secondary": "#65a30d",
        "sidebar": "#0f1f18", "sidebar_border": "#1b3328",
        "sidebar_primary": "#84cc16", "sidebar_text": "#0f1f18",
        "workspace": "#f0faf7", "card": "#ffffff", "surface": "#f4f8f6",
        "text": "#0c1f17", "muted": "#5b7469", "border": "#dbe9e3",
    },
    {
        "id": "royal", "label": "Royal Blue", "mode": "dark",
        "primary": "#3b82f6", "secondary": "#38bdf8",
        "sidebar": "#0c1526", "sidebar_border": "#1a2740",
        "sidebar_primary": "#60a5fa", "sidebar_text": "#ffffff",
        "workspace": "#0a1120", "card": "#101a2e", "surface": "#142038",
        "text": "#eef4ff", "muted": "#9fb0cc", "border": "#22304a",
    },
    {
        "id": "royal", "label": "Royal Blue Light", "mode": "light",
        "primary": "#2563eb", "secondary": "#0284c7",
        "sidebar": "#0c1526", "sidebar_border": "#1a2740",
        "sidebar_primary": "#60a5fa", "sidebar_text": "#ffffff",
        "workspace": "#f0f6ff", "card": "#ffffff", "surface": "#f4f8ff",
        "text": "#0f1b33", "muted": "#5b6f94", "border": "#dbe6f7",
    },
    {
        "id": "lavender", "label": "Lavender", "mode": "dark",
        "primary": "#a78bfa", "secondary": "#c084fc",
        "sidebar": "#150f24", "sidebar_border": "#251b3d",
        "sidebar_primary": "#c4b5fd", "sidebar_text": "#ffffff",
        "workspace": "#110c1d", "card": "#1a1330", "surface": "#1f1740",
        "text": "#f4efff", "muted": "#b3a6d1", "border": "#2d2348",
    },
    {
        "id": "lavender", "label": "Lavender Light", "mode": "light",
        "primary": "#8b5cf6", "secondary": "#a855f7",
        "sidebar": "#150f24", "sidebar_border": "#251b3d",
        "sidebar_primary": "#c4b5fd", "sidebar_text": "#ffffff",
        "workspace": "#f8f5ff", "card": "#ffffff", "surface": "#f4f0ff",
        "text": "#1c1430", "muted": "#6d6190", "border": "#e5ddf5",
    },
    {
        "id": "pink", "label": "Baby Pink", "mode": "light",
        "primary": "#ec6fa3", "secondary": "#f9a8d4",
        "sidebar": "#fdf1f5", "sidebar_border": "#f0d6e2",
        "sidebar_primary": "#ec6fa3", "sidebar_text": "#4a2f3a",
        "workspace": "#fbe8ee", "card": "#ffffff", "surface": "#fff4f8",
        "text": "#4a2f3a", "muted": "#a17d8c", "border": "#f5d9e3",
    },
    {
        "id": "pink", "label": "Baby Pink Dark", "mode": "dark",
        "primary": "#f472b6", "secondary": "#f9a8d4",
        "sidebar": "#2a0d1d", "sidebar_border": "#421531",
        "sidebar_primary": "#f472b6", "sidebar_text": "#ffffff",
        "workspace": "#1c0a14", "card": "#24101c", "surface": "#2a1422",
        "text": "#ffe4f1", "muted": "#c99ab4", "border": "#3c2030",
    },
    {
        "id": "ocean", "label": "Ocean", "mode": "dark",
        "primary": "#06b6d4", "secondary": "#0ea5e9",
        "sidebar": "#081a20", "sidebar_border": "#12303c",
        "sidebar_primary": "#22d3ee", "sidebar_text": "#ffffff",
        "workspace": "#06161c", "card": "#0c1f27", "surface": "#102632",
        "text": "#ecfeff", "muted": "#9fc6d0", "border": "#1c3c48",
    },
    {
        "id": "ocean", "label": "Ocean Light", "mode": "light",
        "primary": "#0891b2", "secondary": "#0284c7",
        "sidebar": "#081a20", "sidebar_border": "#12303c",
        "sidebar_primary": "#22d3ee", "sidebar_text": "#ffffff",
        "workspace": "#ecfeff", "card": "#ffffff", "surface": "#f0fbfd",
        "text": "#0b2b33", "muted": "#4d7a86", "border": "#d3eef3",
    },
    {
        "id": "slate", "label": "Slate", "mode": "dark",
        "primary": "#64748b", "secondary": "#94a3b8",
        "sidebar": "#0f1622", "sidebar_border": "#1c2738",
        "sidebar_primary": "#94a3b8", "sidebar_text": "#ffffff",
        "workspace": "#0c1119", "card": "#131a26", "surface": "#161f2e",
        "text": "#f1f5f9", "muted": "#a2b0c2", "border": "#243042",
    },
    {
        "id": "slate", "label": "Slate Light", "mode": "light",
        "primary": "#475569", "secondary": "#64748b",
        "sidebar": "#0f1622", "sidebar_border": "#1c2738",
        "sidebar_primary": "#94a3b8", "sidebar_text": "#ffffff",
        "workspace": "#f1f5f9", "card": "#ffffff", "surface": "#f4f7fb",
        "text": "#172033", "muted": "#5d6b82", "border": "#dbe1ea",
    },
    {
        "id": "sunset", "label": "Sunset", "mode": "dark",
        "primary": "#f97316", "secondary": "#ef4444",
        "sidebar": "#1f1008", "sidebar_border": "#3a1d0f",
        "sidebar_primary": "#fb923c", "sidebar_text": "#ffffff",
        "workspace": "#160b05", "card": "#1f120a", "surface": "#281810",
        "text": "#fff5ee", "muted": "#d0a98f", "border": "#3c2818",
    },
    {
        "id": "sunset", "label": "Sunset Light", "mode": "light",
        "primary": "#ea580c", "secondary": "#dc2626",
        "sidebar": "#1f1008", "sidebar_border": "#3a1d0f",
        "sidebar_primary": "#fb923c", "sidebar_text": "#ffffff",
        "workspace": "#fff7f0", "card": "#ffffff", "surface": "#fff4ea",
        "text": "#2a1508", "muted": "#8a6a52", "border": "#f0ddcf",
    },
    {
        "id": "crimson", "label": "Crimson", "mode": "dark",
        "primary": "#dc2626", "secondary": "#f97316",
        "sidebar": "#1f0a0a", "sidebar_border": "#3a1414",
        "sidebar_primary": "#f87171", "sidebar_text": "#ffffff",
        "workspace": "#160606", "card": "#200c0c", "surface": "#291111",
        "text": "#fff0f0", "muted": "#d2a0a0", "border": "#3d2020",
    },
    {
        "id": "crimson", "label": "Crimson Light", "mode": "light",
        "primary": "#dc2626", "secondary": "#f97316",
        "sidebar": "#1f0a0a", "sidebar_border": "#3a1414",
        "sidebar_primary": "#f87171", "sidebar_text": "#ffffff",
        "workspace": "#fff5f5", "card": "#ffffff", "surface": "#fff0f0",
        "text": "#2a0a0a", "muted": "#8a5a5a", "border": "#f2d7d7",
    },
]

US_TIMEZONES = [
    {"value": "America/New_York", "label": "Eastern (NY)"},
    {"value": "America/Chicago", "label": "Central (IL/TX)"},
    {"value": "America/Denver", "label": "Mountain (CO)"},
    {"value": "America/Phoenix", "label": "Mountain (AZ)"},
    {"value": "America/Los_Angeles", "label": "Pacific (CA)"},
    {"value": "America/Anchorage", "label": "Alaska"},
    {"value": "Pacific/Honolulu", "label": "Hawaii"},
]


@frappe.whitelist(allow_guest=True)
def get_theme_config():
    """Return available themes (dark + light per accent) for Settings → Appearance."""
    return {"themes": PORTAL_THEMES, "timezones": US_TIMEZONES}


@frappe.whitelist()
def set_my_timezone(timezone):
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Not authenticated")
    allowed = [t["value"] for t in US_TIMEZONES]
    if timezone not in allowed:
        frappe.throw("Invalid timezone. Pick one from the predefined list.")
    agent = _find_sales_agent(user, frappe.db.get_value("User", user, "email"))
    if not agent:
        frappe.throw("No Sales Agent profile linked to this account.")
    frappe.db.set_value("Sales Agent", agent["name"], "portal_timezone", timezone)
    frappe.db.commit()
    return {"timezone": timezone}


def _get_user_timezone(user):
    """Read the sales agent's portal_timezone; falls back to None."""
    if not user or user == "Guest":
        return None
    agent = _find_sales_agent(user, frappe.db.get_value("User", user, "email"))
    if not agent:
        return None
    return agent.get("portal_timezone") or None
