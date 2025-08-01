# apps/cclms/cclms/utils/atm_lead_cleaner.py
import re

def format_phone_number(phone, country):
    if not phone:
        return phone
    phone = re.sub(r"\D", "", phone)
    if country in ["USA", "Canada"] and len(phone) >= 10:
        return f"{phone[-10:-7]}-{phone[-7:-4]}-{phone[-4:]}"
    elif country == "Australia" and len(phone) >= 9:
        return f"{phone[-9:-6]}-{phone[-6:-3]}-{phone[-3:]}"
    return phone

def clean_text(value):
    if not value:
        return ""
    return re.sub(r"[\s:;,.\']+$", "", value.strip())

def clean_atm_leads():
    import frappe
    leads = frappe.get_all("ATM Leads", filters={}, fields=["name", "business_phone_number", "personal_cell_phone", "country",
                                                             "email", "owner_name", "business_name", "city", "state", "state_code"])
    for lead in leads:
        doc = frappe.get_doc("ATM Leads", lead.name)
        doc.business_phone_number = format_phone_number(doc.business_phone_number, doc.country)
        doc.personal_cell_phone = format_phone_number(doc.personal_cell_phone, doc.country)
        doc.email = clean_text(doc.email)
        doc.owner_name = clean_text(doc.owner_name)
        doc.business_name = clean_text(doc.business_name)
        doc.city = clean_text(doc.city)
        doc.state = clean_text(doc.state)
        doc.state_code = clean_text(doc.state_code)
        doc.save()
    frappe.db.commit()
    return "Cleaned all ATM Lead records."
