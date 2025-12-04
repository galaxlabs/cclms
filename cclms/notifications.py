import frappe

EVENTS = {
    "approve_date": "Lead Approved",
    "sign_date": "Lead Signed",
    "convert_date": "Lead Converted",
    "install_date": "Lead Installed",
    "remove_date": "Lead Removed",
    "sign_rejected": "Sign Rejected",
}

def atm_lead_after_save(doc, method):
    old = doc.get_doc_before_save() or frappe._dict()

    # we send notification to KPI agent
    agent = doc.kpi_agent or doc.executive_name
    user = get_user_for_agent(agent)

    if not user:
        return

    for fieldname, event_label in EVENTS.items():
        old_val = getattr(old, fieldname, None)
        new_val = getattr(doc, fieldname, None)

        # only when field changes from empty -> filled
        if not old_val and new_val:
            create_notification(user, doc, event_label)


def get_user_for_agent(agent_name):
    if not agent_name:
        return None
    return frappe.db.get_value("Sales Agent", agent_name, "user_id")


def create_notification(user, doc, event_label):
    nl = frappe.new_doc("Notification Log")
    nl.for_user = user
    nl.type = "Alert"
    nl.subject = f"{event_label}: {doc.business_name or doc.name}"
    nl.document_type = doc.doctype
    nl.document_name = doc.name
    nl.insert(ignore_permissions=True)

    # trigger client side notification refresh
    frappe.publish_realtime("notification_update", after_commit=True)
