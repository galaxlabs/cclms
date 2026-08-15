import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime


@frappe.whitelist()
def schedule_follow_up(lead_name, follow_up_time=None, priority="Normal", notes=None, assign=None):
    """Create a follow-up schedule for a lead. Optionally auto-assign an agent."""
    if not lead_name or not frappe.db.exists("ATM Leads", lead_name):
        frappe.throw(_("ATM Lead not found"))
    lead = frappe.get_doc("ATM Leads", lead_name)
    follow_up_time = follow_up_time or now_datetime()

    doc = frappe.get_doc({
        "doctype": "Follow-up Schedule",
        "lead": lead_name,
        "business_name": lead.business_name or "",
        "business_phone": lead.business_phone_number or "",
        "company": lead.company or "",
        "priority": priority or "Normal",
        "follow_up_time": follow_up_time,
        "status": "Scheduled",
        "notes": notes or "",
    })
    if assign:
        doc.assigned_to = assign
        doc.assigned_branch = frappe.db.get_value("Sales Agent", assign, "branch") or ""
        doc.status = "Scheduled"
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "business_name": doc.business_name, "follow_up_time": str(doc.follow_up_time)}


@frappe.whitelist()
def auto_assign_due(company=None, branch=None):
    """Round-robin auto-assign due/unassigned follow-ups to Sales Agents of the branch."""
    filters = [["status", "in", ["Scheduled", "Due"]], ["follow_up_time", "<=", add_to_date(now_datetime(), minutes=5)]]
    if company:
        filters.append(["company", "=", company])
    if not frappe.db.exists("DocType", "Follow-up Schedule"):
        return {"assigned": 0}

    unassigned = frappe.get_all(
        "Follow-up Schedule",
        filters=filters + [["assigned_to", "is", "not set"]],
        fields=["name", "company", "assigned_branch", "priority"],
        order_by="follow_up_time asc",
        limit_page_length=100,
    )
    if not unassigned:
        return {"assigned": 0}

    agents = _round_robin_pool(branch)
    if not agents:
        return {"assigned": 0, "reason": "no-agents"}

    assigned = 0
    idx = 0
    for row in unassigned:
        agent = agents[idx % len(agents)]
        idx += 1
        branch_val = frappe.db.get_value("Sales Agent", agent, "branch") or ""
        frappe.db.set_value("Follow-up Schedule", row.name, {
            "assigned_to": agent,
            "assigned_branch": branch_val,
            "status": "Due",
        }, update_modified=False)
        assigned += 1
    frappe.db.commit()
    return {"assigned": assigned}


@frappe.whitelist()
def due_follow_ups(agent=None, company=None, limit=50):
    """Follow-ups due for an agent (used by portal + tracker agent)."""
    filters = [["follow_up_time", "<=", add_to_date(now_datetime(), minutes=5)], ["status", "in", ["Scheduled", "Due"]]]
    if agent:
        filters.append(["assigned_to", "=", agent])
    if company:
        filters.append(["company", "=", company])
    rows = frappe.get_all(
        "Follow-up Schedule",
        filters=filters,
        fields=["name", "lead", "business_name", "business_phone", "company", "priority", "follow_up_time", "status", "assigned_to", "assigned_branch", "notes"],
        order_by="follow_up_time asc",
        limit_page_length=limit,
    )
    return rows


@frappe.whitelist()
def next_dial_task(agent=None, company=None):
    """Return the single next due dial task for an agent (for the tracker auto-dial)."""
    due = due_follow_ups(agent=agent, company=company, limit=1)
    return due[0] if due else None


@frappe.whitelist()
def mark_dialed(name, result=None):
    """Mark a follow-up as dialed (called by the tracker agent when it places the call)."""
    if not name or not frappe.db.exists("Follow-up Schedule", name):
        frappe.throw(_("Follow-up not found"))
    frappe.db.set_value("Follow-up Schedule", name, {
        "status": "Dialing",
        "dialed_at": now_datetime(),
        "dial_result": result or "",
    }, update_modified=True)
    frappe.db.commit()
    return {"ok": True, "name": name, "status": "Dialing"}


@frappe.whitelist()
def complete_follow_up(name, result=None, notes=None):
    """Mark a follow-up completed."""
    if not name or not frappe.db.exists("Follow-up Schedule", name):
        frappe.throw(_("Follow-up not found"))
    updates = {"status": "Completed", "completed_at": now_datetime()}
    if result:
        updates["dial_result"] = result
    if notes:
        updates["notes"] = notes
    frappe.db.set_value("Follow-up Schedule", name, updates, update_modified=True)
    frappe.db.commit()
    return {"ok": True, "name": name, "status": "Completed"}


@frappe.whitelist()
def convert_follow_up_to_lead(name, company=None, workflow_state="Pending", address=None, city=None, state=None, state_code=None, zip_code=None, full_address=None):
    """Follow-up-first flow: after a positive call, convert the follow-up into an ATM Lead.

    Creates an ATM Leads record from the follow-up's business data (if the follow-up
    isn't already linked to a lead) and marks the follow-up Completed.
    """
    if not name or not frappe.db.exists("Follow-up Schedule", name):
        frappe.throw(_("Follow-up not found"))
    fu = frappe.get_doc("Follow-up Schedule", name)
    if fu.lead and frappe.db.exists("ATM Leads", fu.lead):
        return {"ok": True, "lead": fu.lead, "already_linked": True}

    company = company or fu.company or (fu.assigned_to and frappe.db.get_value("Sales Agent", fu.assigned_to, "company")) or None
    if not company:
        frappe.throw(_("Select an operator company to create the ATM Lead"))

    full_address = full_address or address or fu.business_address or ""
    lead = frappe.get_doc({
        "doctype": "ATM Leads",
        "company": company,
        "business_name": fu.business_name or "",
        "business_phone_number": fu.business_phone or "",
        "owner_name": fu.operating_company or "",
        "address": address or fu.business_address or "",
        "full_address": full_address,
        "city": city or fu.city or "",
        "state": state or fu.state or "",
        "state_code": state_code or fu.state_code or "",
        "zip_code": zip_code or fu.zip_code or "",
        "workflow_state": "Draft",
        "executive_name": fu.assigned_to or None,
        "status": "Draft",
    })
    lead.insert(ignore_permissions=True)

    # Move to the requested state if it differs from Draft (valid workflow transition).
    if workflow_state and workflow_state != "Draft":
        frappe.db.set_value("ATM Leads", lead.name, "workflow_state", workflow_state, update_modified=True)

    frappe.db.set_value("Follow-up Schedule", fu.name, {
        "lead": lead.name,
        "status": "Completed",
        "completed_at": now_datetime(),
    }, update_modified=True)
    frappe.db.commit()
    return {"ok": True, "lead": lead.name, "follow_up": fu.name}


@frappe.whitelist()
def my_follow_ups(agent=None, status=None, limit=100):
    """Follow-ups for the current portal user's sales agent."""
    agent = agent or _resolve_current_sales_agent()
    filters = [["assigned_to", "=", agent]] if agent else []
    if status:
        filters.append(["status", "=", status])
    rows = frappe.get_all(
        "Follow-up Schedule",
        filters=filters,
        fields=["name", "lead", "business_name", "business_phone", "company", "priority", "follow_up_time", "status", "assigned_to", "assigned_branch", "notes", "dial_result"],
        order_by="follow_up_time asc",
        limit_page_length=limit,
    )
    return rows


def _resolve_current_sales_agent():
    user = frappe.session.user
    if not user or user == "Guest":
        return None
    if frappe.db.exists("DocType", "Sales Agent"):
        name = frappe.db.get_value("Sales Agent", {"user": user}, "name")
        if name:
            return name
    return None


def _round_robin_pool(branch=None):
    """Sales Agents available for assignment, optionally scoped by branch, enabled only."""
    filters = {"enable": 1}
    if branch:
        filters["branch"] = branch
    if not frappe.db.exists("DocType", "Sales Agent"):
        return []
    return frappe.get_all("Sales Agent", filters=filters, pluck="name", order_by="creation asc")
