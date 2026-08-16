from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class FollowUpSettings(Document):
    pass


@frappe.whitelist()
def get_followup_settings():
    """Return follow-up settings + domain list for the portal/SPA."""
    settings = frappe.get_single("Follow-up Settings") if frappe.db.exists("DocType", "Follow-up Settings") else None
    domains = []
    if settings and settings.domains:
        domains = [d.domain for d in settings.domains if d.domain]
    if not domains:
        from cclms.call_centre_lead_management_system.doctype.operator_companies.operator_companies import BUSINESS_DOMAINS
        domains = BUSINESS_DOMAINS
    return {
        "domains": domains,
        "default_domain": (settings.default_domain if settings and settings.default_domain else (domains[0] if domains else "")),
        "slot_start_hour": (settings.slot_start_hour if settings and settings.slot_start_hour else 8),
        "slot_end_hour": (settings.slot_end_hour if settings and settings.slot_end_hour else 20),
        "slot_minutes": (settings.slot_minutes if settings and settings.slot_minutes else 5),
        "require_company": bool(settings and settings.require_company),
        "require_domain": bool(settings and settings.require_domain),
    }
