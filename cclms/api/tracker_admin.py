import secrets
import string

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.password import update_password


ADMIN_ROLES = {"System Manager", "Director", "Security Manager"}


def _require_tracker_admin():
    roles = set(frappe.get_roles(frappe.session.user))
    if roles.intersection(ADMIN_ROLES):
        return
    frappe.throw(_("You are not allowed to manage tracker devices"), frappe.PermissionError)


def _tracker_doc(name):
    _require_tracker_admin()
    return frappe.get_doc("Tracker Device", name)


def _append_note(doc, message):
    stamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
    actor = frappe.session.user
    line = f"[{stamp}] {actor}: {message}"
    existing = (doc.notes or "").strip()
    doc.notes = f"{existing}\n{line}".strip() if existing else line


def _random_password(length=14):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@frappe.whitelist()
def block_tracker_device(name, reason=None):
    doc = _tracker_doc(name)
    doc.active = 0
    _append_note(doc, f"Device blocked. Reason: {reason or 'No reason provided'}")
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "name": doc.name, "active": doc.active}


@frappe.whitelist()
def unblock_tracker_device(name, note=None):
    doc = _tracker_doc(name)
    doc.active = 1
    _append_note(doc, f"Device unblocked. Note: {note or 'No note provided'}")
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "name": doc.name, "active": doc.active}


@frappe.whitelist()
def reset_tracked_user_password(name, new_password=None):
    doc = _tracker_doc(name)
    tracked_user = (doc.tracked_user or "").strip()
    if not tracked_user:
        frappe.throw(_("Tracker Device has no tracked user"))
    if not frappe.db.exists("User", tracked_user):
        frappe.throw(_("Tracked user does not exist"))

    password = new_password or _random_password()
    update_password(tracked_user, password)
    _append_note(doc, f"Desk password reset for tracked user {tracked_user}")
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "tracked_user": tracked_user, "new_password": password}
