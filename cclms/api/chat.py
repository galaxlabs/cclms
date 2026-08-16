import frappe
from frappe import _


def _resolve_username(user=None):
    user = user or frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Not authenticated"))
    return user


def _contacts():
    rows = frappe.get_all(
        "User",
        filters=[["enabled", "=", 1], ["name", "not in", ["Guest", "Administrator"]]],
        fields=["name", "full_name", "user_image"],
        order_by="full_name asc",
        limit_page_length=200,
    )
    return [{"name": r.name, "full_name": r.full_name or r.name, "user_image": r.user_image} for r in rows]


@frappe.whitelist()
def list_contacts():
    return _contacts()


@frappe.whitelist()
def send_message(receiver, message):
    if not receiver or not message:
        frappe.throw(_("Receiver and message are required"))
    sender = _resolve_username()
    doc = frappe.get_doc({
        "doctype": "Chat Message",
        "sender": sender,
        "receiver": receiver,
        "message": message,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "sender": doc.sender, "receiver": doc.receiver, "message": doc.message, "creation": str(doc.creation)}


@frappe.whitelist()
def get_conversation(other_user, after=None):
    """Return messages between current user and other_user (both directions)."""
    if not other_user:
        frappe.throw(_("other_user is required"))
    me = _resolve_username()
    filters = [
        ["sender", "in", [me, other_user]],
        ["receiver", "in", [me, other_user]],
    ]
    rows = frappe.get_all(
        "Chat Message",
        filters=filters,
        fields=["name", "sender", "receiver", "message", "is_read", "creation"],
        order_by="creation asc",
        limit_page_length=500,
    )
    return rows or []


@frappe.whitelist()
def my_conversations():
    """Return distinct contacts the current user has exchanged messages with, plus latest message."""
    me = _resolve_username()
    rows = frappe.get_all(
        "Chat Message",
        filters=[["sender", "=", me], ["receiver", "=", me]],
        fields=["name", "sender", "receiver", "message", "creation"],
        order_by="creation desc",
        limit_page_length=1000,
    )
    convos = {}
    for r in rows:
        other = r.sender if r.sender != me else r.receiver
        key = other
        if key and key not in convos:
            convos[key] = {"other_user": key, "last_message": r.message, "last_time": str(r.creation)}
    return list(convos.values())


@frappe.whitelist()
def mark_read(other_user):
    me = _resolve_username()
    frappe.db.sql(
        """UPDATE `tabChat Message` SET is_read=1, read_at=%s
           WHERE receiver=%s AND sender=%s AND is_read=0""",
        (frappe.utils.now_datetime(), me, other_user),
    )
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def unread_count():
    me = _resolve_username()
    count = frappe.db.count("Chat Message", {"receiver": me, "is_read": 0})
    return {"count": count}
