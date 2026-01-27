import frappe
from frappe import _
from frappe.model.workflow import (
    get_workflow_name,
    get_transitions as wf_get_transitions,
    apply_workflow,
)

@frappe.whitelist()
def get_workflow_meta(doctype: str):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    wf_name = get_workflow_name(doctype)
    if not wf_name:
        return {"doctype": doctype, "workflow_name": None, "states": []}

    wf = frappe.get_doc("Workflow", wf_name)
    states = [d.state for d in (wf.states or []) if d.state]
    return {"doctype": doctype, "workflow_name": wf_name, "states": states}


@frappe.whitelist()
def get_transitions(doctype: str, docname: str):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    doc = frappe.get_doc(doctype, docname)
    transitions = wf_get_transitions(doc, frappe.session.user) or []

    out = []
    for t in transitions:
        out.append({
            "action": t.get("action"),
            "next_state": t.get("next_state"),
            "allowed": True
        })
    return out


@frappe.whitelist()
def apply_action(doctype: str, docname: str, action: str):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    doc = frappe.get_doc(doctype, docname)
    doc = apply_workflow(doc, action)

    return {
        "name": doc.name,
        "workflow_state": getattr(doc, "workflow_state", None),
        "modified": doc.modified
    }
