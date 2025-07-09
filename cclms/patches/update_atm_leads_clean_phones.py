import re
import frappe

def extract_digits(phone):
    return re.sub(r'\D', '', phone or '')

def format_to_us_number(phone):
    digits = extract_digits(phone)
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    else:
        print(f"⚠️ Skipping invalid: '{phone}' ➜ digits: '{digits}' (length: {len(digits)})")
        return phone

# ✅ Required for Frappe to run this patch
def execute():
    leads = frappe.get_all("ATM Leads", fields=["name", "business_phone_number", "personal_cell_phone"])
    for lead in leads:
        updated = False

        new_business = format_to_us_number(lead.business_phone_number)
        new_personal = format_to_us_number(lead.personal_cell_phone)

        if new_business != lead.business_phone_number:
            frappe.db.set_value("ATM Leads", lead.name, "business_phone_number", new_business)
            updated = True
            print(f"✅ Updated business phone: {lead.business_phone_number} ➜ {new_business}")

        if new_personal != lead.personal_cell_phone:
            frappe.db.set_value("ATM Leads", lead.name, "personal_cell_phone", new_personal)
            updated = True
            print(f"✅ Updated personal phone: {lead.personal_cell_phone} ➜ {new_personal}")

        if updated:
            frappe.db.commit()

