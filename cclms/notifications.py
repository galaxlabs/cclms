import frappe

from cclms.utils.communication_utils import create_system_notification

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

    old_state = getattr(old, "workflow_state", None)
    new_state = getattr(doc, "workflow_state", None)
    if new_state and old_state != new_state:
        create_notification(
            user,
            doc,
            f"Lead moved to {new_state}",
            body=f"{doc.business_name or doc.name} changed from {old_state or 'Draft'} to {new_state}",
            indicator=_workflow_indicator(new_state),
        )


def get_user_for_agent(agent_name):
    if not agent_name:
        return None
    return frappe.db.get_value("Sales Agent", agent_name, "user_id")


def create_notification(user, doc, event_label):
    subject = f"{event_label}: {doc.business_name or doc.name}"
    create_system_notification(
        user,
        doc,
        subject,
        title="ATM Lead Update",
        body=subject,
        indicator="green",
        notification_type="Alert",
    )


def _workflow_indicator(state):
    value = (state or "").lower()
    if any(word in value for word in ("approved", "signed", "installed", "converted")):
        return "green"
    if any(word in value for word in ("rejected", "removed", "cancelled")):
        return "red"
    return "orange"
