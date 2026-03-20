import frappe
from frappe.utils import now_datetime


def enrich_location(location_name, force=0):
    if not frappe.db.exists("BTM Location", location_name):
        frappe.throw(f"BTM Location not found: {location_name}")

    location = frappe.get_doc("BTM Location", location_name)
    existing = frappe.db.get_value(
        "Business Enrichment",
        {"location": location.name, "provider": "external_registry"},
        "name",
    ) if frappe.db.exists("DocType", "Business Enrichment") else None

    if existing and not int(force or 0):
        return frappe.get_doc("Business Enrichment", existing).as_dict()

    endpoint = frappe.conf.get("open_llc_hub_url")
    api_key = frappe.conf.get("open_llc_hub_api_key")
    payload = {
        "business_name": location.location_name,
        "state": location.state,
        "zip_code": location.zip_code,
    }

    status = "Pending"
    response = {}
    if endpoint and api_key:
        from frappe.integrations.utils import make_post_request

        try:
            response = make_post_request(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            ) or {}
            status = "Matched" if response else "No Match"
        except Exception:
            status = "Error"
            response = {"error": frappe.get_traceback()}

    doc = frappe.get_doc("Business Enrichment", existing) if existing else frappe.new_doc("Business Enrichment")
    doc.location = location.name
    doc.provider = "external_registry"
    doc.status = status
    doc.business_name = response.get("business_name") or location.location_name
    doc.state = response.get("state") or location.state
    doc.zip_code = response.get("zip_code") or location.zip_code
    doc.external_id = response.get("id")
    doc.payload_json = frappe.as_json(response, indent=2)
    doc.last_checked_on = now_datetime()
    if status == "Matched":
        doc.matched_on = now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()
