import frappe
from frappe import _
from frappe.utils import getdate, nowdate, add_days


def _current_employee():
    user = frappe.session.user
    if not user or user == "Guest":
        return None
    # Sales Agent → employee link first
    agent = frappe.db.get_value("Sales Agent", {"user": user}, "employee")
    if agent:
        return agent
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


@frappe.whitelist()
def my_leaves(status=None, from_date=None, to_date=None, limit=100):
    """Leave applications for the current employee."""
    emp = _current_employee()
    filters = [["employee", "=", emp]] if emp else []
    if status:
        filters.append(["status", "=", status])
    if from_date and to_date:
        filters.append(["from_date", "between", [from_date, to_date]])
    return frappe.get_all(
        "Leave Application",
        filters=filters,
        fields=["name", "employee", "employee_name", "leave_type", "from_date", "to_date",
                "total_leave_days", "status", "description", "leave_approver_name", "posting_date"],
        order_by="posting_date desc",
        limit_page_length=limit,
    )


@frappe.whitelist()
def leave_types():
    return frappe.get_all("Leave Type", fields=["name", "max_leaves_allowed", "is_lwp"], order_by="leave_type_name asc")


@frappe.whitelist()
def leave_balance(employee=None, leave_type=None):
    """Opening + credited - consumed per leave type (from Leave Ledger)."""
    emp = employee or _current_employee()
    if not emp:
        return []
    filters = [["employee", "=", emp]]
    if leave_type:
        filters.append(["leave_type", "=", leave_type])
    rows = frappe.get_all("Leave Ledger Entry", filters=filters, fields=["leave_type", "leaves"])
    bal = {}
    for r in rows:
        bal[r["leave_type"]] = bal.get(r["leave_type"], 0) + (r["leaves"] or 0)
    out = [{"leave_type": k, "balance": round(v, 2)} for k, v in bal.items()]
    return sorted(out, key=lambda x: x["leave_type"])


@frappe.whitelist()
def create_leave(leave_type, from_date, to_date, description=None, half_day=0, half_day_date=None):
    """Create a Leave Application for the current employee."""
    emp = _current_employee()
    if not emp:
        frappe.throw(_("No Employee linked to your account."))
    emp_name = frappe.db.get_value("Employee", emp, "employee_name") or ""
    doc = frappe.get_doc({
        "doctype": "Leave Application",
        "employee": emp,
        "employee_name": emp_name,
        "leave_type": leave_type,
        "from_date": from_date,
        "to_date": to_date,
        "half_day": 1 if half_day in (1, "1", True) else 0,
        "half_day_date": half_day_date or "",
        "description": description or "",
        "company": frappe.db.get_value("Employee", emp, "company") or "",
        "department": frappe.db.get_value("Employee", emp, "department") or "",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "employee": doc.employee, "leave_type": doc.leave_type,
            "from_date": str(doc.from_date), "to_date": str(doc.to_date), "total_leave_days": doc.total_leave_days,
            "status": doc.status}


@frappe.whitelist()
def list_all_leaves(status=None, from_date=None, to_date=None, employee=None, limit=200):
    """All leave applications (HR view)."""
    filters = []
    if status:
        filters.append(["status", "=", status])
    if employee:
        filters.append(["employee", "=", employee])
    if from_date and to_date:
        filters.append(["from_date", "between", [from_date, to_date]])
    return frappe.get_all(
        "Leave Application",
        filters=filters,
        fields=["name", "employee", "employee_name", "leave_type", "from_date", "to_date",
                "total_leave_days", "status", "description", "leave_approver_name"],
        order_by="posting_date desc",
        limit_page_length=limit,
    )


@frappe.whitelist()
def approve_leave(name, status="Approved", comment=None):
    """Approve / Reject / Cancel a leave application (HR action)."""
    if not name or not frappe.db.exists("Leave Application", name):
        frappe.throw(_("Leave application not found"))
    status = status.title()
    if status not in ("Approved", "Rejected", "Cancelled"):
        frappe.throw(_("Invalid status"))
    doc = frappe.get_doc("Leave Application", name)
    doc.status = status
    if comment:
        doc.add_comment("Comment", comment)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": name, "status": doc.status}
