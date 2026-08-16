import frappe
from frappe import _
import json


def _resolve_username(user=None):
    user = user or frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Not authenticated"))
    return user


def _contacts():
    """Only ACTIVE sales agents (enable=1) with a linked user, not all users."""
    rows = frappe.get_all(
        "Sales Agent",
        filters=[["enable", "=", 1]],
        fields=["name", "full_name", "user", "email"],
        order_by="full_name asc",
        limit_page_length=200,
    )
    out = []
    for r in rows:
        email = r.get("user") or r.get("email")
        if not email:
            continue
        out.append({"name": email, "full_name": r.get("full_name") or r.get("name") or email, "sales_agent": r.get("name")})
    return out


@frappe.whitelist()
def list_contacts():
    return _contacts()


@frappe.whitelist()
def send_message(receiver=None, message=None, attachment_url=None, attachment_name=None, group_name=None, is_pinned=0, mention_users=None, linked_doctype=None, linked_name=None):
    if not receiver and not group_name:
        frappe.throw(_("Receiver or group is required"))
    if not message:
        frappe.throw(_("Message is required"))
    sender = _resolve_username()
    doc = frappe.get_doc({
        "doctype": "Chat Message",
        "sender": sender,
        "receiver": receiver or "",
        "message": message,
        "attachment_url": attachment_url or "",
        "attachment_name": attachment_name or "",
        "group_name": group_name or "",
        "is_pinned": 1 if is_pinned in (1, "1", True) else 0,
        "mention_users": mention_users or "",
        "linked_doctype": linked_doctype or "",
        "linked_name": linked_name or "",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "sender": doc.sender, "receiver": doc.receiver, "message": doc.message,
            "creation": str(doc.creation), "attachment_url": doc.attachment_url, "attachment_name": doc.attachment_name,
            "group_name": doc.group_name, "is_pinned": doc.is_pinned, "mention_users": doc.mention_users,
            "linked_doctype": doc.linked_doctype, "linked_name": doc.linked_name}


def _message_filters(other_user=None, group_name=None):
    me = _resolve_username()
    if group_name:
        return [["group_name", "=", group_name]]
    if not other_user:
        return None
    return [
        ["sender", "in", [me, other_user]],
        ["receiver", "in", [me, other_user]],
    ]


@frappe.whitelist()
def get_conversation(other_user=None, group_name=None, after=None):
    filters = _message_filters(other_user=other_user, group_name=group_name)
    if filters is None:
        return []
    return frappe.get_all(
        "Chat Message",
        filters=filters,
        fields=["name", "sender", "receiver", "message", "is_read", "creation",
                "attachment_url", "attachment_name", "group_name", "is_pinned", "mention_users",
                "linked_doctype", "linked_name"],
        order_by="creation asc",
        limit_page_length=1000,
    )


@frappe.whitelist()
def my_conversations():
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
        if other and other not in convos:
            convos[other] = {"other_user": other, "last_message": r.message, "last_time": str(r.creation)}
    return list(convos.values())


@frappe.whitelist()
def mark_read(other_user=None, group_name=None):
    me = _resolve_username()
    if group_name:
        frappe.db.sql(
            """UPDATE `tabChat Message` SET is_read=1, read_at=%s
               WHERE group_name=%s AND sender<>%s AND is_read=0""",
            (frappe.utils.now_datetime(), group_name, me),
        )
    elif other_user:
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


# ── Groups ──────────────────────────────────────────────────────────────
@frappe.whitelist()
def create_group(group_name, members=None):
    """Create a chat group with member emails (list). Adds the creator automatically."""
    me = _resolve_username()
    members = members or []
    if isinstance(members, str):
        try:
            members = json.loads(members)
        except Exception:
            members = []
    member_list = list({me, *members})
    doc = frappe.get_doc({
        "doctype": "Chat Group",
        "group_name": group_name,
        "created_by": me,
    })
    for m in member_list:
        doc.append("members", {"user": m})
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "group_name": doc.group_name, "members": member_list}


@frappe.whitelist()
def list_groups():
    me = _resolve_username()
    groups = frappe.get_all(
        "Chat Group",
        filters=[["members", "like", f"%{me}%"]],
        fields=["name", "group_name", "created_by"],
        order_by="modified desc",
    )
    out = []
    for g in groups:
        out.append({
            "name": g["name"],
            "group_name": g["group_name"],
            "created_by": g["created_by"],
            "group_member_count": frappe.db.count("Chat Group Member", {"parent": g["name"]}),
        })
    return out


# ── Pinned messages ────────────────────────────────────────────────────
@frappe.whitelist()
def pin_message(name):
    if not name or not frappe.db.exists("Chat Message", name):
        frappe.throw(_("Message not found"))
    me = _resolve_username()
    frappe.db.set_value("Chat Message", name, {"is_pinned": 1}, update_modified=True)
    # Mirror into a Chat Group pinned child if group message
    msg = frappe.db.get_value("Chat Message", name, ["group_name", "message"], as_dict=True)
    if msg and msg.get("group_name"):
        grp = frappe.db.get_value("Chat Group", {"group_name": msg["group_name"]}, "name")
        if grp:
            g = frappe.get_doc("Chat Group", grp)
            exists = any(p.chat_message == name for p in g.pinned_messages)
            if not exists:
                g.append("pinned_messages", {"message_text": msg["message"], "pinned_by": me, "pinned_at": frappe.utils.now_datetime(), "chat_message": name})
                g.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "name": name}


@frappe.whitelist()
def unpin_message(name):
    if not name or not frappe.db.exists("Chat Message", name):
        return {"ok": True}
    frappe.db.set_value("Chat Message", name, {"is_pinned": 0}, update_modified=True)
    msg = frappe.db.get_value("Chat Message", name, "group_name")
    if msg:
        grp = frappe.db.get_value("Chat Group", {"group_name": msg}, "name")
        if grp:
            g = frappe.get_doc("Chat Group", grp)
            g.pinned_messages = [p for p in g.pinned_messages if p.chat_message != name]
            g.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "name": name}


@frappe.whitelist()
def pinned_messages(group_name=None):
    me = _resolve_username()
    if group_name:
        grp = frappe.db.get_value("Chat Group", {"group_name": group_name}, "name")
        if not grp:
            return []
        return frappe.get_all("Chat Pinned Message", filters={"parent": grp}, fields=["message_text", "pinned_by", "pinned_at", "chat_message"])
    return frappe.get_all("Chat Message", filters={"is_pinned": 1, "sender": me}, fields=["name", "sender", "message", "creation", "group_name"], order_by="creation desc")


# ── Attach a cclms record as a document reference ──────────────────────
@frappe.whitelist()
def attach_record(doctype, name):
    """Attach a cclms record (ATM Lead / Follow-up / Campaign / Task / Project / File) to a chat message."""
    if not doctype or not name:
        frappe.throw(_("doctype and name required"))
    if not frappe.db.exists("DocType", doctype) or not frappe.db.exists(doctype, name):
        frappe.throw(_("Record not found"))
    title = frappe.db.get_value(doctype, name, "name")
    label = title
    for f in ("business_name", "subject", "title", "campaign_name", "subject_name", "file_name"):
        if frappe.db.has_column(doctype, f):
            v = frappe.db.get_value(doctype, name, f)
            if v:
                label = v
                break
    return {"doctype": doctype, "name": name, "label": label}


# ── AI Bot (integration point) ─────────────────────────────────────────
def _search_records(query, settings):
    """Gather context rows across enabled tools; returns list of {kind, text}."""
    results = []
    q = f"%{query}%"
    try:
        if settings.get("enable_lead_search"):
            leads = frappe.get_all("ATM Leads", filters=[["business_name", "like", q]], fields=["name", "business_name", "workflow_state", "company", "executive_name"], limit_page_length=10)
            for r in leads:
                results.append({"kind": "ATM Lead", "text": f"{r.business_name} | {r.company} | {r.workflow_state} | {r.executive_name}"})
    except Exception:
        pass
    try:
        if settings.get("enable_followup_search"):
            fups = frappe.get_all("Follow-up Schedule", filters=[["business_name", "like", q]], fields=["name", "business_name", "status", "follow_up_time"], limit_page_length=10)
            for r in fups:
                results.append({"kind": "Follow-up", "text": f"{r.business_name} | {r.status} | {r.follow_up_time}"})
    except Exception:
        pass
    try:
        if settings.get("enable_campaign_search"):
            camps = frappe.get_all("Sales Campaign", filters=[["campaign_name", "like", q]], fields=["name", "campaign_name", "status", "assigned_agent"], limit_page_length=10)
            for r in camps:
                results.append({"kind": "Campaign", "text": f"{r.campaign_name} | {r.status} | {r.assigned_agent}"})
    except Exception:
        pass
    try:
        if settings.get("enable_document_search"):
            docs = frappe.get_all("File", filters=[["file_name", "like", q]], fields=["name", "file_name", "file_url"], limit_page_length=10)
            for r in docs:
                results.append({"kind": "Document", "text": f"{r.file_name} | {r.file_url}"})
    except Exception:
        pass
    return results


def _call_ai(settings, query, context):
    """Call the configured provider. Returns dict {ok, reply, error}."""
    api_key = settings.get_password("api_key") if settings.get("api_key") else ""
    if not api_key:
        return {"ok": False, "error": "AI API key not configured. Set it in AI Settings (System Manager)."}
    import urllib.request
    provider = settings.get("provider") or "openai"
    model = settings.get("model") or "gpt-4o-mini"
    base = (settings.get("base_url") or "").rstrip("/")
    context_text = "\n".join([f"- [{r['kind']}] {r['text']}" for r in context]) or "(no matching records found)"
    system = (
        "You are the XG Hub assistant inside a CRM for ATM sales agents. "
        "Answer briefly using the provided CRM context. If context is empty say so and suggest creating a lead or follow-up."
    )
    payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": f"Question: {query}\n\nCRM context:\n{context_text}"}]}
    if provider == "openai":
        url = base or "https://api.openai.com/v1"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    elif provider == "openrouter":
        url = base or "https://openrouter.ai/api/v1"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    elif provider == "gemini":
        url = base or f"https://generativelanguage.googleapis.com/v1beta"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": f"{system}\n\n{query}\n\nCRM context:\n{context_text}"}]}]}
    else:
        return {"ok": False, "error": f"Unsupported provider: {provider}"}
    req = urllib.request.Request(f"{url}/chat/completions", data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
            if provider == "gemini":
                text = body["candidates"][0]["content"]["parts"][0]["text"]
            else:
                text = body["choices"][0]["message"]["content"]
            return {"ok": True, "reply": text}
    except Exception as e:
        return {"ok": False, "error": f"AI call failed: {e}"}


@frappe.whitelist()
def bot_ask(query, history=None):
    """Answer a question about leads / follow-ups / campaigns / documents.

    Integration point: reads AI Settings; if the API key is configured it calls the
    provider, otherwise returns the searched context so the UI can still show results.
    """
    if not query:
        frappe.throw(_("Query required"))
    me = _resolve_username()
    settings = frappe.get_cached_doc("AI Settings")
    context = _search_records(query, settings.as_dict())
    res = _call_ai(settings, query, context)
    if res.get("ok"):
        return {"ok": True, "reply": res["reply"], "context": context, "from": "ai"}
    return {"ok": True, "reply": None, "context": context, "error": res.get("error"), "from": "search"}
