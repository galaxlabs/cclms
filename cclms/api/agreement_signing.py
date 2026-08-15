import frappe
from frappe import _
from frappe.utils import now_datetime


LEAD_FILL_MAP = {
    "business_name": ("business_name", "Business Name"),
    "business_type": ("business_type", "Business Type"),
    "address": ("address", "Address"),
    "full_address": ("full_address", "Full Address"),
    "city": ("city", "City"),
    "state": ("state", "State"),
    "state_code": ("state_code", "State Code"),
    "zip_code": ("zip_code", "ZIP Code"),
    "company": ("company", "Company"),
    "owner_name": ("owner_name", "Owner Name"),
    "email": ("email", "Email"),
    "business_phone_number": ("business_phone_number", "Business Phone"),
    "personal_cell_phone": ("personal_cell_phone", "Personal Phone"),
    "executive_name": ("executive_name", "Executive"),
    "post_date": ("post_date", "Post Date"),
    "lead_name": (None, "Lead Name"),
}

# KPF (Kiosk Placement Form) template labels → value sources.
# Priority: Agreement Sign Form field → ATM Lead field → literal.
KPF_FILL_MAP = {
    "location legal entity": ("location_legal_entity", "owner_name"),
    "effective date": ("effective_date", "post_date"),
    "location dba name": ("location_name", "business_name"),
    "phone": ("phone", "business_phone_number"),
    "email": ("email", "email"),
    "address": ("address", "full_address"),
    "address to be used for payment": ("address", "full_address"),
    "sales contact": ("sales_contact", "executive_name"),
    "account manager": ("account_manager", None),
    "tenant or landlord": ("tenant_or_landlord", None),
    "lease end date": ("contract_end_date", None),
    "term": ("title", None),
    "county": ("county", None),
    "distributor": ("distributer", None),
    "premises": ("premises", "business_name"),
    "additional entity": ("additonal_entity", None),
    "effective fee revenue": ("transection_fees", None),
    "per trans": ("transection_fees", None),
    "flat fee": ("flat_fee", None),
    "company name": ("oprator_name", "company"),
    "owner name": ("owner_name", "owner_name"),
    "title": ("title", None),
}


def _template_component_label(component):
    """Best-effort label for an esign component: its content hint or field key."""
    for key in ("label", "name", "field_label", "placeholder", "content"):
        value = component.get(key)
        if value:
            return str(value).strip()
    return ""


def _fill_value_for_component(component, lead_values):
    """Resolve a component's value from ATM lead fields by label matching."""
    label = _template_component_label(component)
    label_lower = label.casefold()

    # Direct match on component key/name
    for key, (fieldname, field_label) in LEAD_FILL_MAP.items():
        if label_lower in {key.casefold(), field_label.casefold()}:
            return lead_values.get(fieldname) or (lead_values.get("name") if key == "lead_name" else "")

    # Substring match on business-name, address, city, etc.
    for fieldname in ("business_name", "full_address", "address", "city", "state", "zip_code", "company", "owner_name", "email", "business_phone_number"):
        field_label = dict(LEAD_FILL_MAP.values()).get(fieldname, "")
        if fieldname.casefold() in label_lower or (field_label and field_label.casefold() in label_lower):
            return lead_values.get(fieldname) or ""

    return ""


@frappe.whitelist()
def get_atm_lead_fill_data(lead_name):
    """Return a label -> value map of ATM Leads fields usable for agreement fill."""
    if not frappe.db.exists("ATM Leads", lead_name):
        frappe.throw(_("ATM Lead not found"))
    doc = frappe.get_doc("ATM Leads", lead_name)

    values = {fieldname: doc.get(fieldname) or "" for fieldname, (fn, _) in LEAD_FILL_MAP.items() if fn}
    values["name"] = doc.name
    return {
        "lead_name": doc.name,
        "business_name": doc.business_name or "",
        "business_type": doc.business_type or "",
        "address": doc.address or "",
        "full_address": doc.full_address or "",
        "city": doc.city or "",
        "state": doc.state or "",
        "state_code": doc.state_code or "",
        "zip_code": doc.zip_code or "",
        "company": doc.company or "",
        "owner_name": doc.owner_name or "",
        "email": doc.email or "",
        "business_phone_number": doc.business_phone_number or "",
        "personal_cell_phone": doc.personal_cell_phone or "",
        "executive_name": doc.executive_name or "",
        "post_date": str(doc.post_date or ""),
    }


@frappe.whitelist()
def fill_esign_document_from_lead(document_name, lead_name):
    """Auto-fill an esign DocumentList's text components from an ATM Lead."""
    if not frappe.db.exists("DocumentList", document_name):
        frappe.throw(_("Document not found"))
    if not frappe.db.exists("ATM Leads", lead_name):
        frappe.throw(_("ATM Lead not found"))

    lead_values = get_atm_lead_fill_data(lead_name)

    doc = frappe.get_doc("DocumentList", document_name)
    try:
        components = frappe.parse_json(doc.document_json_data)
    except Exception:
        components = doc.document_json_data or []

    filled = 0
    if isinstance(components, dict):
        components = components.get("components") or components.get("fields") or []

    for component in components or []:
        ctype = (component.get("type") or "").lower()
        if ctype not in ("text", "date", "checkbox"):
            continue
        value = _fill_value_for_component(component, lead_values)
        if value:
            component["content"] = value
            filled += 1

    doc.document_json_data = frappe.as_json(components)
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"filled": filled, "document_name": document_name, "lead_name": lead_name}


@frappe.whitelist()
def fill_kpf_document_from_lead(document_name, lead_name):
    """Auto-fill a Kiosk Placement Form esign document from the ATM Lead + Agreement Sign Form."""
    if not frappe.db.exists("DocumentList", document_name):
        frappe.throw(_("Document not found"))
    if not frappe.db.exists("ATM Leads", lead_name):
        frappe.throw(_("ATM Lead not found"))

    lead = frappe.get_doc("ATM Leads", lead_name)
    # Locate an Agreement Sign Form for this lead, if any
    agreement = {}
    if frappe.db.exists("DocType", "Agreement Sign Form"):
        row = frappe.db.get_value("Agreement Sign Form", {"lead_name": lead_name}, "*", as_dict=True)
        if row:
            agreement = row

    lead_values = get_atm_lead_fill_data(lead_name)

    def resolve(label):
        label_lower = label.casefold()
        for key, (agreement_field, lead_field) in KPF_FILL_MAP.items():
            if key in label_lower:
                if agreement_field and agreement.get(agreement_field):
                    return agreement[agreement_field]
                if lead_field and lead_values.get(lead_field):
                    return lead_values[lead_field]
                return ""
        return ""

    doc = frappe.get_doc("DocumentList", document_name)
    try:
        components = frappe.parse_json(doc.document_json_data)
    except Exception:
        components = doc.document_json_data or []
    if isinstance(components, dict):
        components = components.get("components") or components.get("fields") or []

    filled = 0
    for component in components or []:
        ctype = (component.get("type") or "").lower()
        if ctype not in ("text", "date", "checkbox"):
            continue
        label = _template_component_label(component)
        value = resolve(label)
        if value:
            component["content"] = value
            filled += 1

    doc.document_json_data = frappe.as_json(components)
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"filled": filled, "document_name": document_name, "lead_name": lead_name}


@frappe.whitelist()
def link_lead_to_esign_document(document_name, lead_name):
    """Associate an esign document with an ATM Lead for sign-back tracking."""
    if not frappe.db.exists("DocumentList", document_name):
        frappe.throw(_("Document not found"))
    if not frappe.db.exists("ATM Leads", lead_name):
        frappe.throw(_("ATM Lead not found"))
    if not frappe.db.exists("Custom Field", {"dt": "DocumentList", "fieldname": "atm_lead_link"}):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "DocumentList",
            "fieldname": "atm_lead_link",
            "fieldtype": "Link",
            "options": "ATM Leads",
            "label": "ATM Lead",
            "insert_after": "document_title",
        }).insert(ignore_permissions=True)
    frappe.db.set_value("DocumentList", document_name, "atm_lead_link", lead_name, update_modified=True)
    frappe.db.commit()
    return {"ok": True, "document_name": document_name, "lead_name": lead_name}


@frappe.whitelist()
def get_esign_documents_for_lead(lead_name):
    """List esign documents linked to an ATM Lead."""
    if not frappe.db.exists("DocType", "DocumentList"):
        return []
    if not frappe.db.exists("Custom Field", {"dt": "DocumentList", "fieldname": "atm_lead_link"}):
        return []
    rows = frappe.get_all(
        "DocumentList",
        filters={"atm_lead_link": lead_name},
        fields=["name", "document_title", "iscompleted", "isrejected", "validated_pdf", "document_created_at"],
        order_by="creation desc",
        limit_page_length=20,
    )
    return rows


@frappe.whitelist()
def mark_lead_signed_from_esign(document_name):
    """After an esign document is completed, mark the linked ATM Lead as Signed."""
    if not frappe.db.exists("DocumentList", document_name):
        frappe.throw(_("Document not found"))
    if not frappe.db.exists("Custom Field", {"dt": "DocumentList", "fieldname": "atm_lead_link"}):
        return {"ok": False, "reason": "no-link-field"}

    lead_name = frappe.db.get_value("DocumentList", document_name, "atm_lead_link")
    if not lead_name:
        return {"ok": False, "reason": "no-lead-link"}

    doc = frappe.get_doc("ATM Leads", lead_name)
    if doc.workflow_state not in ("Signed", "Installed", "Converted"):
        doc.workflow_state = "Signed"
        if not doc.sign_date:
            doc.sign_date = now_datetime().strftime("%Y-%m-%d")
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"ok": True, "lead_name": lead_name, "workflow_state": "Signed"}
    return {"ok": True, "lead_name": lead_name, "workflow_state": doc.workflow_state}


# ---------------------------------------------------------------------------
# Dynamic per-company contract configuration
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_company_contract_settings(company):
    """Return the active contract settings configured for an operator company."""
    if not company or not frappe.db.exists("Operator Companies", company):
        frappe.throw(_("Operator company not found"))
    names = frappe.get_all("Operator Contract Setting", filters={"operator_company": company, "enabled": 1}, order_by="creation asc", pluck="name")
    settings = []
    for name in names:
        doc = frappe.get_doc("Operator Contract Setting", name)
        settings.append(_contract_dict(doc, company))
    return {"company": company, "contracts": settings}


@frappe.whitelist()
def get_contract_settings_for_lead(lead_name, state=None):
    """Pick the matching contract setting for a lead's operator company + state.

    Prefers a contract whose lead_state_trigger matches the given state; otherwise
    falls back to the first enabled contract for the company (dynamic per company).
    """
    if not frappe.db.exists("ATM Leads", lead_name):
        frappe.throw(_("ATM Lead not found"))
    lead = frappe.get_doc("ATM Leads", lead_name)
    company = lead.company
    state = state or lead.workflow_state

    names = frappe.get_all("Operator Contract Setting", filters={"operator_company": company, "enabled": 1}, order_by="creation asc", pluck="name")
    if not names:
        return {"company": company, "contract_title": None}

    docs = [frappe.get_doc("Operator Contract Setting", n) for n in names]
    for doc in docs:
        if doc.lead_state_trigger and doc.lead_state_trigger == state:
            return _contract_dict(doc, company)
    # Fall back to the first enabled contract
    return _contract_dict(docs[0], company)


def _contract_dict(doc, company):
    # Build fill map from the structured child table (Contract Field Mapping).
    fill_fields = {}
    for m in doc.get("field_mappings") or []:
        if not m.get("enabled", 1):
            continue
        label = m.get("template_field_label")
        if not label:
            continue
        if m.get("source_doctype") == "Static":
            fill_fields[label] = {"source": "Static", "value": m.get("static_value")}
        else:
            fill_fields[label] = {"source": m.get("source_doctype") or "ATM Leads", "value": m.get("atm_leads_field")}
    if not fill_fields:
        legacy = _safe_parse_json(doc.fill_fields_json)
        fill_fields = {label: {"source": "ATM Leads", "value": field} for label, field in legacy.items()}

    return {
        "company": company,
        "contract_title": doc.contract_title,
        "template_name": doc.template_name,
        "template_file": doc.template_file,
        "contract_attachment": doc.contract_attachment,
        "base_fee": doc.base_fee,
        "fee_type": doc.fee_type,
        "revenue_share_percent": doc.revenue_share_percent,
        "flat_fee": doc.flat_fee,
        "special_terms": doc.special_terms,
        "fill_fields": fill_fields,
    }


@frappe.whitelist()
def create_agreement_from_lead(lead_name, contract_index=0):
    """Create a pre-filled esign DocumentList for an ATM Lead using the operator's contract config.

    Returns a document that the portal can open for preview and guest signing.
    """
    if not frappe.db.exists("ATM Leads", lead_name):
        frappe.throw(_("ATM Lead not found"))

    lead = frappe.get_doc("ATM Leads", lead_name)
    contract = get_contract_settings_for_lead(lead_name)
    if not contract.get("contract_title"):
        frappe.throw(_("No contract settings configured for company {0}").format(lead.company))

    # Build component list from the contract's fill-field mapping.
    components = []
    for label, field in (contract.get("fill_fields") or {}).items():
        components.append({
            "type": "text",
            "label": label,
            "content": "",
            "position": {"top": 100 + len(components) * 30, "left": 100},
            "fontSize": 12,
            "pageNo": 1,
        })

    # If an esign template exists, load its real components instead.
    template_data = None
    if contract.get("template_name") and frappe.db.exists("TempleteList", contract["template_name"]):
        try:
            template_doc = frappe.get_doc("TempleteList", contract["template_name"])
            template_data = {
                "components": frappe.parse_json(template_doc.templete_json_data),
                "base_pdf": template_doc.base_pdf_data,
            }
        except Exception:
            template_data = None

    if template_data and isinstance(template_data["components"], list):
        components = template_data["components"]
        base_pdf = template_data["base_pdf"]
    else:
        base_pdf = frappe.as_json({"pages": []})

    document_title = f"{contract['contract_title']} - {lead.business_name or lead.name}"
    doc = frappe.get_doc({
        "doctype": "DocumentList",
        "document_title": document_title,
        "template_title": contract.get("template_name") or contract["contract_title"],
        "owner_email": frappe.session.user,
        "document_json_data": frappe.as_json(components),
        "base_pdf_datad": base_pdf,
        "document_created_at": now_datetime(),
        "iscompleted": 0,
        "isrejected": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    # Link back to the lead and auto-fill from lead + agreement form.
    link_lead_to_esign_document(doc.name, lead_name)
    fill_fields = contract.get("fill_fields") or {}
    filled = _fill_document_from_map(doc.name, lead_name, fill_fields)

    return {
        "document_name": doc.name,
        "document_title": document_title,
        "company": lead.company,
        "contract_title": contract.get("contract_title"),
        "template_name": contract.get("template_name"),
        "contract_attachment": contract.get("contract_attachment"),
        "filled": filled,
        "lead_name": lead_name,
        "open_url": f"/app/document-list/{doc.name}",
    }


@frappe.whitelist()
def request_agreement_for_lead(lead_name, contract_index=0, guest_email=None):
    """Create a pre-filled agreement for a lead and (optionally) assign a guest to sign it."""
    result = create_agreement_from_lead(lead_name, contract_index)
    document_name = result["document_name"]
    if guest_email:
        assigned = frappe.as_json({guest_email: {"email": guest_email, "signed": False}})
        frappe.db.set_value("DocumentList", document_name, "assigned_users", assigned, update_modified=True)
        frappe.db.set_value("DocumentList", document_name, "isnoteditable", 1, update_modified=True)
        frappe.db.commit()
        result["guest_email"] = guest_email
        result["share_url"] = f"/esignDash/doc/{document_name}"
    return result


@frappe.whitelist()
def get_lead_agreement_options(lead_name):
    """Return the contract options available for a lead's operator company (for the portal picker)."""
    if not frappe.db.exists("ATM Leads", lead_name):
        frappe.throw(_("ATM Lead not found"))
    lead = frappe.get_doc("ATM Leads", lead_name)
    result = get_company_contract_settings(lead.company)
    return {
        "company": lead.company,
        "lead_name": lead_name,
        "workflow_state": lead.workflow_state,
        "contracts": result.get("contracts") or [],
    }


def _fill_document_from_map(document_name, lead_name, fill_fields):
    """Fill DocumentList text components by label using a label -> field map."""
    if not fill_fields:
        return 0
    lead_values = get_atm_lead_fill_data(lead_name)
    agreement = {}
    if frappe.db.exists("DocType", "Agreement Sign Form"):
        row = frappe.db.get_value("Agreement Sign Form", {"lead_name": lead_name}, "*", as_dict=True)
        if row:
            agreement = row

    doc = frappe.get_doc("DocumentList", document_name)
    try:
        components = frappe.parse_json(doc.document_json_data)
    except Exception:
        components = doc.document_json_data or []
    if isinstance(components, dict):
        components = components.get("components") or components.get("fields") or []

    filled = 0
    for component in components or []:
        ctype = (component.get("type") or "").lower()
        if ctype not in ("text", "date", "checkbox"):
            continue
        label = _template_component_label(component)
        mapping = fill_fields.get(label)
        if not mapping:
            continue
        # mapping is either {"source": "...", "value": "..."} or legacy bare string
        if isinstance(mapping, dict):
            source = mapping.get("source") or "ATM Leads"
            field = mapping.get("value")
            if source == "Static":
                value = mapping.get("value")
            elif source == "Agreement Sign Form":
                value = agreement.get(field) if field else None
            else:
                value = lead_values.get(field) if field else None
        else:
            value = agreement.get(mapping) if agreement.get(mapping) else lead_values.get(mapping)
        if value:
            component["content"] = str(value)
            filled += 1

    doc.document_json_data = frappe.as_json(components)
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return filled


def _safe_parse_json(value):
    if not value:
        return {}
    try:
        parsed = frappe.parse_json(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}
