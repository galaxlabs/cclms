import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

from cclms.utils.communication_utils import OPERATIONS_EMAIL_ACCOUNTS


def _current_user():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Login required"))
    return user


def _user_roles(user):
    return set(frappe.get_roles(user))


def _workflow_states_for_user(user):
    roles = list(_user_roles(user))
    if not roles:
        return []

    rows = frappe.get_all(
        "Workflow Document State",
        filters={"parent": "Track", "allow_edit": ["in", roles]},
        fields=["state", "allow_edit"],
        order_by="idx asc",
    )
    return rows


def _notification_rows(user, limit=20):
    fields = ["name", "subject", "type", "document_type", "document_name", "creation", "read"]
    return frappe.get_all(
        "Notification Log",
        filters={"for_user": user},
        fields=fields,
        order_by="creation desc",
        limit_page_length=limit,
    )


def _todo_rows(user, limit=20):
    if not frappe.db.exists("DocType", "ToDo"):
        return []

    return frappe.get_all(
        "ToDo",
        filters={"allocated_to": user, "status": ["not in", ["Closed", "Cancelled"]]},
        fields=["name", "description", "priority", "status", "reference_type", "reference_name", "date", "modified"],
        order_by="date asc, modified desc",
        limit_page_length=limit,
    )


def _operations_email_rows(user, limit=20):
    if not frappe.db.exists("DocType", "Communication"):
        return []

    authorized_accounts = frappe.get_all(
        "User Email",
        filters={"parent": user, "parenttype": "User", "email_account": ["in", sorted(OPERATIONS_EMAIL_ACCOUNTS)]},
        pluck="email_account",
    )
    if not authorized_accounts:
        return []

    since = add_to_date(now_datetime(), days=-7)
    return frappe.get_all(
        "Communication",
        filters={
            "sent_or_received": "Received",
            "email_account": ["in", authorized_accounts],
            "creation": [">=", since],
        },
        fields=["name", "subject", "sender", "sender_full_name", "email_account", "creation", "status"],
        order_by="creation desc",
        limit_page_length=limit,
    )


def _lead_action_rows(user, limit=20):
    workflow_rows = _workflow_states_for_user(user)
    states = [row.state for row in workflow_rows if row.get("state")]
    if not states:
        return []

    rows = frappe.get_all(
        "ATM Leads",
        filters={"workflow_state": ["in", states]},
        fields=[
            "name",
            "business_name",
            "company",
            "workflow_state",
            "executive_name",
            "modified",
            "address",
            "zip_code",
        ],
        order_by="modified desc",
        limit_page_length=limit,
    )

    allow_map = {row.state: row.allow_edit for row in workflow_rows}
    for row in rows:
        row["required_role"] = allow_map.get(row.get("workflow_state"))
    return rows


def _deal_action_rows(user, limit=20):
    agent_filters = None
    meta = frappe.get_meta("Sales Agent")
    fieldnames = {field.fieldname for field in meta.fields}
    if "user" in fieldnames:
        agent_filters = {"user": user}
    elif "email" in fieldnames:
        agent_filters = {"email": user}

    agent_names = frappe.get_all("Sales Agent", filters=agent_filters, pluck="name") if agent_filters else []
    fields = [
        "name",
        "status",
        "operator_company",
        "location",
        "sales_agent",
        "sales_agent_name_text",
        "assigned_agent",
        "modified",
    ]

    rows = frappe.get_all(
        "Operator Deal",
        filters={"assigned_agent": user},
        fields=fields,
        order_by="modified desc",
        limit_page_length=limit,
    )

    if agent_names:
        seen = {row.name for row in rows}
        extra = frappe.get_all(
            "Operator Deal",
            filters={"sales_agent": ["in", agent_names]},
            fields=fields,
            order_by="modified desc",
            limit_page_length=limit,
        )
        for row in extra:
            if row.name not in seen:
                rows.append(row)
                seen.add(row.name)

    rows.sort(key=lambda row: row.get("modified") or "", reverse=True)
    return rows[:limit]


def _summary_counts(data):
    return {
        "notifications": len(data["notifications"]),
        "todos": len(data["todos"]),
        "lead_actions": len(data["lead_actions"]),
        "deal_actions": len(data["deal_actions"]),
        "emails": len(data["emails"]),
    }


@frappe.whitelist()
def dashboard(limit=20):
    user = _current_user()
    limit = max(5, min(int(limit or 20), 100))

    data = {
        "user": user,
        "roles": sorted(_user_roles(user)),
        "notifications": _notification_rows(user, limit=limit),
        "todos": _todo_rows(user, limit=limit),
        "lead_actions": _lead_action_rows(user, limit=limit),
        "deal_actions": _deal_action_rows(user, limit=limit),
        "emails": _operations_email_rows(user, limit=limit),
    }
    data["summary"] = _summary_counts(data)
    return data
