import secrets
import string

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.password import update_password


ADMIN_ROLES = {"System Manager", "Director", "Security Manager"}


def _require_admin():
    roles = set(frappe.get_roles(frappe.session.user))
    if roles.intersection(ADMIN_ROLES):
        return
    frappe.throw(_("You are not allowed to manage device profiles"), frappe.PermissionError)


def _device_profile(name):
    _require_admin()
    return frappe.get_doc("Device Profile", name)


def _append_note(doc, message):
    stamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
    actor = frappe.session.user
    line = f"[{stamp}] {actor}: {message}"
    existing = (doc.notes or "").strip()
    doc.notes = f"{existing}\n{line}".strip() if existing else line


def _random_password(length=14):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _sync_status_to_tracker_device(doc):
    tracker_name = doc.tracker_device or frappe.db.get_value("Tracker Device", {"device_id": doc.device_id}, "name")
    if not tracker_name:
        return
    frappe.db.set_value(
        "Tracker Device",
        tracker_name,
        {
            "active": 0 if (doc.status or "").lower() == "blocked" else 1,
            "tracked_user": doc.tracked_user,
            "employee": doc.employee,
            "allowed_service_user": doc.allowed_service_user,
            "machine_name": doc.machine_name,
            "notes": doc.notes,
        },
        update_modified=False,
    )


@frappe.whitelist()
def block_device_profile(name, reason=None):
    doc = _device_profile(name)
    doc.status = "Blocked"
    _append_note(doc, f"Device blocked. Reason: {reason or 'No reason provided'}")
    doc.save(ignore_permissions=True)
    _sync_status_to_tracker_device(doc)
    frappe.db.commit()
    return {"ok": True, "name": doc.name, "status": doc.status}


@frappe.whitelist()
def unblock_device_profile(name, note=None):
    doc = _device_profile(name)
    doc.status = "Active"
    _append_note(doc, f"Device unblocked. Note: {note or 'No note provided'}")
    doc.save(ignore_permissions=True)
    _sync_status_to_tracker_device(doc)
    frappe.db.commit()
    return {"ok": True, "name": doc.name, "status": doc.status}


@frappe.whitelist()
def reset_profile_user_password(name, new_password=None):
    doc = _device_profile(name)
    tracked_user = (doc.tracked_user or "").strip()
    if not tracked_user:
        frappe.throw(_("Device Profile has no tracked user"))
    if not frappe.db.exists("User", tracked_user):
        frappe.throw(_("Tracked user does not exist"))

    password = new_password or _random_password()
    update_password(tracked_user, password)
    _append_note(doc, f"Desk password reset for tracked user {tracked_user}")
    doc.save(ignore_permissions=True)
    _sync_status_to_tracker_device(doc)
    frappe.db.commit()
    return {"ok": True, "tracked_user": tracked_user, "new_password": password}
