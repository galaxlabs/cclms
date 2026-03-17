import frappe
from frappe.utils import strip_html_tags, now_datetime, get_datetime, add_to_date

# --- EMAIL LOGIC ---

def handle_incoming_operations_email(doc, method=None):
    """Triggered from hooks.py on Communication after_insert"""
    if doc.sent_or_received == "Received" and doc.email_account == "Oprations":
        
        # 1. Security: Only run Gemini/Alerts for emails from the last 10 minutes
        # This prevents crashing during your bulk history pull
        ten_mins_ago = add_to_date(now_datetime(), minutes=-10)
        if get_datetime(doc.creation) < get_datetime(ten_mins_ago):
            return

        # 2. Notify Authorized Users
        notify_authorized_inbox_users(doc)
        
        # 3. Generate Gemini Draft
        generate_gemini_draft(doc)

def notify_authorized_inbox_users(doc):
    authorized_users = frappe.get_all("User Email", filters={
        "email_account": "Oprations",
        "parenttype": "User"
    }, fields=["parent"])

    recipients = list(set([u.parent for u in authorized_users]))

    for user in recipients:
        if user == frappe.session.user: continue
        
        # Create Bell Notification
        frappe.get_doc({
            "doctype": "Notification Log",
            "for_user": user,
            "subject": f"New Email: {doc.subject or 'No Subject'}",
            "type": "Alert",
            "document_type": "Communication",
            "document_name": doc.name
        }).insert(ignore_permissions=True)

def generate_gemini_draft(doc):
    api_key = frappe.db.get_single_value('Google Maps Settings', 'api_key')
    if not api_key: return

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    clean_content = strip_html_tags(doc.content or "")
    
    try:
        from frappe.integrations.utils import make_post_request
        payload = {"contents": [{"parts": [{"text": f"Draft a professional reply: {clean_content}"}]}]}
        response = make_post_request(url, json=payload)

        if response and "candidates" in response:
            ai_text = response["candidates"][0]["content"]["parts"][0]["text"]
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": "Communication",
                "reference_name": doc.name,
                "content": f"🤖 **Gemini AI Suggestion:**\n\n{ai_text}"
            }).insert(ignore_permissions=True)
    except Exception:
        pass

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

    # 1. Notify the Record Owner (The Sales Agent who created it)
    if doc.owner != user_who_saved:
        msg = f"Document {doc.name} moved to state: {current_state}"
        create_system_notification(doc.owner, doc, msg)

    # 2. Notify the Next Approvers based on the Workflow 'allow_edit' Role
    # Your JSON shows different roles for different states
    wf_name = "Track"
    
    # Fetch the role that is allowed to edit in the NEW state
    allowed_role = frappe.db.get_value("Workflow Document State", 
        {"parent": wf_name, "state": current_state}, "allow_edit")

    if allowed_role:
        # Get all users with this specific role
        approvers = frappe.get_all("Has Role", 
            filters={"role": allowed_role, "parenttype": "User"}, 
            fields=["parent"])
        
        for appr in approvers:
            if appr.parent != user_who_saved:
                msg = f"Action Required: {doc.name} is now in '{current_state}' (Role: {allowed_role})"
                create_system_notification(appr.parent, doc, msg)

def create_system_notification(recipient, doc, message):
    """Creates the Notification Log and triggers a Realtime popup"""
    # A. Create the Bell Notification
    frappe.get_doc({
        "doctype": "Notification Log",
        "for_user": recipient,
        "subject": message,
        "type": "Alert",
        "document_type": doc.doctype,
        "document_name": doc.name
    }).insert(ignore_permissions=True)

    # B. Trigger Realtime Popup (For Chrome/Desk)
    frappe.publish_realtime(
        event="notification", # This matches the JS listener we discussed
        message={
            "subject": message,
            "document_type": doc.doctype,
            "document_name": doc.name
        },
        user=recipient
    )