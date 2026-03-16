import frappe
from frappe.utils import strip_html_tags

def handle_incoming_operations_email(doc, method=None):
    """
    Main trigger called by hooks.py on Communication 'after_insert'
    """
    # Only run for Received emails in the 'Oprations' account
    if doc.sent_or_received == "Received" and doc.email_account == "Oprations":
        
        # 1. Notify only users who have 'Oprations' enabled in their User profile
        notify_authorized_inbox_users(doc)
        
        # 2. Generate Gemini Draft
        generate_gemini_draft(doc)

def notify_authorized_inbox_users(doc):
    # Find users who have 'Oprations' in their 'user_emails' child table
    authorized_users = frappe.get_all("User Email", filters={
        "email_account": "Oprations",
        "parenttype": "User"
    }, fields=["parent"])

    recipients = list(set([u.parent for u in authorized_users]))

    for user in recipients:
        if user == frappe.session.user: continue
        
        frappe.get_doc({
            "doctype": "Notification Log",
            "for_user": user,
            "subject": f"New Operations Email: {doc.subject or 'No Subject'}",
            "type": "Alert",
            "document_type": "Communication",
            "document_name": doc.name
        }).insert(ignore_permissions=True)

def generate_gemini_draft(doc):
    # Pull API Key from Google Maps Settings
    api_key = frappe.db.get_single_value('Google Maps Settings', 'api_key')
    if not api_key:
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    clean_content = strip_html_tags(doc.content or "")
    prompt = f"Draft a professional and concise reply to this customer email: {clean_content}"

    try:
        # Use frappe's robust request handler
        from frappe.integrations.utils import make_post_request
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = make_post_request(url, json=payload)

        if response and "candidates" in response:
            ai_text = response["candidates"][0]["content"]["parts"][0]["text"]
            
            # Insert suggestion as a comment on the email
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": "Communication",
                "reference_name": doc.name,
                "content": f"🤖 **Gemini AI Suggestion:**\n\n{ai_text}"
            }).insert(ignore_permissions=True)
            
    except Exception as e:
        frappe.log_error(f"Gemini Draft Error: {str(e)}", "Communication Utils")