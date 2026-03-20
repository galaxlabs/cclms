import frappe
from frappe.utils import add_to_date, cint, get_datetime, now_datetime, strip_html_tags

OPERATIONS_EMAIL_ACCOUNTS = {"Oprations", "Operations"}
DEFAULT_NOTIFICATION_EVENT = "cclms_notification"
DEFAULT_NOTIFICATION_TITLE = "CCLMS"

# --- EMAIL LOGIC ---

def handle_incoming_operations_email(doc, method=None):
    """Triggered from hooks.py on Communication after_insert"""
    if not is_recent_received_operations_email(doc):
        return

    # 1. Notify authorized users for the inbox
    notify_authorized_inbox_users(doc)

    # 2. Generate Gemini Draft
    generate_gemini_draft(doc)


def is_recent_received_operations_email(doc):
    if getattr(doc, "sent_or_received", None) != "Received":
        return False

    if getattr(doc, "email_account", None) not in OPERATIONS_EMAIL_ACCOUNTS:
        return False

    # Guard against history pulls or backfills generating a storm of alerts.
    ten_mins_ago = add_to_date(now_datetime(), minutes=-10)
    return get_datetime(doc.creation) >= get_datetime(ten_mins_ago)

def notify_authorized_inbox_users(doc):
    recipients = get_operations_inbox_recipients(doc)

    subject = doc.subject or "No Subject"
    sender = doc.sender_full_name or doc.sender or "Unknown Sender"
    message = f"New Operations Email: {subject}"
    body = f"From {sender}"

    for user in recipients:
        create_system_notification(
            user,
            doc,
            message,
            title="Operations Inbox",
            body=body,
            indicator="blue",
            notification_type="Alert",
        )


def get_operations_inbox_recipients(doc=None):
    email_account = getattr(doc, "email_account", None) if doc else None
    candidate_accounts = [email_account] if email_account else []
    candidate_accounts.extend(sorted(OPERATIONS_EMAIL_ACCOUNTS))

    seen = set()
    recipients = []

    for account in candidate_accounts:
        if not account or account in seen:
            continue
        seen.add(account)

        authorized_users = frappe.get_all(
            "User Email",
            filters={"email_account": account, "parenttype": "User"},
            pluck="parent",
        )
        recipients.extend(authorized_users)

    return get_enabled_notification_recipients(recipients)

def generate_gemini_draft(doc):
    api_key = frappe.db.get_single_value('Google Maps Settings', 'api_key')
    if not api_key:
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    clean_content = strip_html_tags(doc.content or "")
    
    try:
        from frappe.integrations.utils import make_post_request
        payload = {"contents": [{"parts": [{"text": f"Draft a professional reply: {clean_content}"}]}]}
        response = make_post_request(url, json=payload)

        if response and "candidates" in response:
            ai_text = response["candidates"][0]["content"]["parts"][0]["text"]
            frappe.get_doc(
                {
                    "doctype": "Comment",
                    "comment_type": "Comment",
                    "reference_doctype": "Communication",
                    "reference_name": doc.name,
                    "content": f"AI Suggestion:\n\n{ai_text}",
                }
            ).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Communication Utils Gemini Draft")

# --- WORKFLOW LOGIC ---

def handle_atm_lead_workflow(doc, method=None):
    """
    Triggered from hooks.py on ATM Leads after_save.
    Handles the 'Track' Workflow notifications.
    """
    # Only run if the state has actually changed
    if not doc.has_value_changed("workflow_state"):
        return

    current_state = doc.workflow_state
    user_who_saved = frappe.session.user

    recipients = set()
    if doc.owner:
        recipients.add(doc.owner)

    allowed_role = frappe.db.get_value(
        "Workflow Document State", {"parent": "Track", "state": current_state}, "allow_edit"
    )

    if allowed_role:
        recipients.update(
            frappe.get_all(
                "Has Role",
                filters={"role": allowed_role, "parenttype": "User"},
                pluck="parent",
            )
        )

    for recipient in get_enabled_notification_recipients(recipients, exclude_users=[user_who_saved]):
        if recipient == doc.owner:
            message = f"Lead {doc.name} moved to {current_state}"
        else:
            message = f"Action Required: {doc.name} is now '{current_state}'"

        create_system_notification(
            recipient,
            doc,
            message,
            title="ATM Lead Workflow",
            body=f"State changed to {current_state}",
            indicator=get_workflow_indicator(current_state),
            notification_type="Alert",
        )


def get_enabled_notification_recipients(users, exclude_users=None):
    exclude_users = set(exclude_users or [])
    normalized_users = []

    for user in users or []:
        if user and user not in exclude_users:
            normalized_users.append(user)

    if not normalized_users:
        return []

    enabled_users = frappe.get_all(
        "User",
        filters={"name": ["in", list(set(normalized_users))], "enabled": 1},
        pluck="name",
    )
    return sorted(set(enabled_users))


def get_workflow_indicator(state):
    state = (state or "").lower()
    if any(word in state for word in ("approved", "installed", "signed", "converted")):
        return "green"
    if any(word in state for word in ("rejected", "cancelled", "removed")):
        return "red"
    return "orange"


def create_system_notification(
    recipient,
    doc,
    message,
    title=None,
    body=None,
    indicator="orange",
    notification_type="Alert",
    event=DEFAULT_NOTIFICATION_EVENT,
):
    """Create a bell notification and push a browser notification payload."""
    if not recipient:
        return

    payload = build_realtime_payload(
        doc,
        message=message,
        title=title,
        body=body,
        indicator=indicator,
        notification_type=notification_type,
    )

    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "for_user": recipient,
            "subject": message,
            "type": notification_type,
            "document_type": doc.doctype,
            "document_name": doc.name,
        }
    ).insert(ignore_permissions=True)

    frappe.publish_realtime(
        event=event,
        message=payload,
        user=recipient,
        after_commit=True,
    )
    frappe.publish_realtime("notification_update", after_commit=True, user=recipient)


def build_realtime_payload(doc, message, title=None, body=None, indicator="orange", notification_type="Alert"):
    return {
        "title": title or DEFAULT_NOTIFICATION_TITLE,
        "subject": message,
        "body": body or message,
        "indicator": indicator,
        "type": notification_type,
        "document_type": doc.doctype,
        "document_name": doc.name,
        "route": ["Form", doc.doctype, doc.name],
        "timestamp": now_datetime().isoformat(),
        "notification_id": f"{doc.doctype}:{doc.name}:{cint(now_datetime().timestamp())}",
    }
