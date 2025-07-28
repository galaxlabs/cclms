import re
import frappe

ALLOWED_COUNTRIES = ["USA", "Canada", "Australia"]

def format_phone_number(phone, country):
    phone = re.sub(r"\D", "", phone or "")
    if country in ["USA", "Canada"] and len(phone) >= 10:
        return f"{phone[-10:-7]}-{phone[-7:-4]}-{phone[-4:]}"
    elif country == "Australia" and len(phone) >= 9:
        return f"{phone[-9:-6]}-{phone[-6:-3]}-{phone[-3:]}"
    return phone

def clean_text(value):
    if not value:
        return ''
    value = re.sub(r"\s{2,}", " ", value)  # Collapse multiple spaces
    value = re.sub(r",+", ",", value)      # Replace multiple commas
    value = re.sub(r"[.,:;]+$", "", value.strip())  # Remove trailing punctuation
    return value.strip()

def execute():
    leads = frappe.get_all("ATM Leads", fields=[
        "name",
        "branch",
        "country",
        "business_phone_number",
        "personal_cell_phone",
        "email",
        "address",
        "full_address",
        "city",
        "state_code",
        "state"
    ])

    for lead in leads:
        if lead.branch != "Karachi" or lead.country not in ALLOWED_COUNTRIES:
            continue

        updates = {}

        # 📞 Phone formatting
        formatted_business = format_phone_number(lead.business_phone_number, lead.country)
        if formatted_business != (lead.business_phone_number or ""):
            updates["business_phone_number"] = formatted_business

        formatted_personal = format_phone_number(lead.personal_cell_phone, lead.country)
        if formatted_personal != (lead.personal_cell_phone or ""):
            updates["personal_cell_phone"] = formatted_personal

        # 📧 Clean email
        if lead.email:
            cleaned_email = clean_text(lead.email)
            if cleaned_email != lead.email:
                updates["email"] = cleaned_email

        # 🏠 Clean address
        if lead.address:
            cleaned_address = clean_text(lead.address)
            if cleaned_address != lead.address:
                updates["address"] = cleaned_address
                updates["full_address"] = cleaned_address

        # 🌆 City, state_code, state cleanup
        for field in ["city", "state_code", "state"]:
            val = lead.get(field)
            if val:
                cleaned_val = clean_text(val)
                if cleaned_val != val:
                    updates[field] = cleaned_val

        # ✅ Save if any changes
        if updates:
            frappe.db.set_value("ATM Leads", lead.name, updates)
            print(f"✅ Updated {lead.name}: {updates}")

    frappe.db.commit()
    print("🎯 Patch execution complete.")

# import re
# import frappe

# def extract_digits(phone):
#     return re.sub(r'\D', '', phone or '')

# def format_to_us_number(phone):
#     digits = extract_digits(phone)
#     if len(digits) == 10:
#         return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
#     else:
#         print(f"⚠️ Skipping invalid: '{phone}' ➜ digits: '{digits}' (length: {len(digits)})")
#         return phone

# # ✅ Required for Frappe to run this patch
# def execute():
#     leads = frappe.get_all("ATM Leads", fields=["name", "business_phone_number", "personal_cell_phone"])
#     for lead in leads:
#         updated = False

#         new_business = format_to_us_number(lead.business_phone_number)
#         new_personal = format_to_us_number(lead.personal_cell_phone)

#         if new_business != lead.business_phone_number:
#             frappe.db.set_value("ATM Leads", lead.name, "business_phone_number", new_business)
#             updated = True
#             print(f"✅ Updated business phone: {lead.business_phone_number} ➜ {new_business}")

#         if new_personal != lead.personal_cell_phone:
#             frappe.db.set_value("ATM Leads", lead.name, "personal_cell_phone", new_personal)
#             updated = True
#             print(f"✅ Updated personal phone: {lead.personal_cell_phone} ➜ {new_personal}")

#         if updated:
#             frappe.db.commit()

