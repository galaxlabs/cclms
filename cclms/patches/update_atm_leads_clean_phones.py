import re
import frappe

def execute():
    print("🚀 Patch is executing!")  # Confirm if it even starts

def extract_digits(phone):
    return re.sub(r'\D', '', phone or '')

def format_phone_number(phone, country):
    if not phone:
        return ""
    digits = extract_digits(phone)
    if country in ["USA", "Canada"] and len(digits) >= 10:
        return f"{digits[-10:-7]}-{digits[-7:-4]}-{digits[-4:]}"
    elif country == "Australia" and len(digits) >= 9:
        return f"{digits[-9:-6]}-{digits[-6:-3]}-{digits[-3:]}"
    return phone.strip()

def clean_text(value):
    if not value:
        return ""

    value = value.strip()

    # Convert common invalid entries to empty
    if value.lower() in ["none", "na", "n/a"]:
        return ""

    value = re.sub(r"\s{2,}", " ", value)         # Collapse multiple spaces
    value = re.sub(r"\s*,\s*", ",", value)        # Normalize comma spacing
    value = re.sub(r",+", ",", value)             # Collapse multiple commas
    value = re.sub(r"[.,:;]+$", "", value)        # Remove ending punctuation
    return value.strip()

def clean_name(value):
    if not value:
        return ""

    value = value.strip()

    if value.lower() in ["none", "na", "n/a"]:
        return ""

    value = re.sub(r"\s{2,}", " ", value)         # Collapse multiple spaces
    value = re.sub(r"[.,:;]+$", "", value)        # Remove trailing punctuation
    return value.strip()

def execute():
    print("🚀 Running patch to clean ATM Leads...")

    leads = frappe.get_all("ATM Leads", fields=[
        "name",
        "country",
        "business_phone_number",
        "personal_cell_phone",
        "address",
        "city",
        "state",
        "state_code",
        "zippostal_code",
        "email",
        "owner_name",
        "business_name"
    ])

    updated_count = 0

    for lead in leads:
        country = lead.get("country") or ""
        if country not in ["USA", "Canada", "Australia"]:
            continue

        updated_fields = {}

        # Phone numbers
        business_clean = format_phone_number(lead.business_phone_number, country)
        if business_clean != (lead.business_phone_number or "").strip():
            updated_fields["business_phone_number"] = business_clean

        personal_clean = format_phone_number(lead.personal_cell_phone, country)
        if personal_clean != (lead.personal_cell_phone or "").strip():
            updated_fields["personal_cell_phone"] = personal_clean

        # Text cleanup
        text_fields = ["address", "city", "state", "state_code", "zippostal_code", "email"]
        for field in text_fields:
            original = (lead.get(field) or "").strip()
            cleaned = clean_text(original)
            if cleaned != original:
                updated_fields[field] = cleaned

        # Name cleanup
        name_fields = ["owner_name", "business_name"]
        for field in name_fields:
            original = (lead.get(field) or "").strip()
            cleaned = clean_name(original)
            if cleaned != original:
                updated_fields[field] = cleaned

        # Apply updates
        if updated_fields:
            frappe.db.set_value("ATM Leads", lead.name, updated_fields)
            print(f"✅ Updated {lead.name}: {updated_fields}")
            updated_count += 1

    frappe.db.commit()
    print(f"🎯 Patch execution complete. Total updated records: {updated_count}")



# import re
# import frappe

# ALLOWED_COUNTRIES = ["USA", "Canada", "Australia"]

# def format_phone_number(phone, country):
#     phone = re.sub(r"\D", "", phone or "")
#     if country in ["USA", "Canada"] and len(phone) >= 10:
#         return f"{phone[-10:-7]}-{phone[-7:-4]}-{phone[-4:]}"
#     elif country == "Australia" and len(phone) >= 9:
#         return f"{phone[-9:-6]}-{phone[-6:-3]}-{phone[-3:]}"
#     return phone

# def clean_text(value):
#     if not value:
#         return ''
#     value = re.sub(r"\s{2,}", " ", value)  # Collapse multiple spaces
#     value = re.sub(r",+", ",", value)      # Replace multiple commas
#     value = re.sub(r"[.,:;]+$", "", value.strip())  # Remove trailing punctuation
#     return value.strip()

# def execute():
#     leads = frappe.get_all("ATM Leads", fields=[
#         "name",
#         "branch",
#         "country",
#         "business_phone_number",
#         "personal_cell_phone",
#         "email",
#         "address",
#         "full_address",
#         "city",
#         "state_code",
#         "state"
#     ])

#     for lead in leads:
#         if lead.branch != "Karachi" or lead.country not in ALLOWED_COUNTRIES:
#             continue

#         updates = {}

#         # 📞 Phone formatting
#         formatted_business = format_phone_number(lead.business_phone_number, lead.country)
#         if formatted_business != (lead.business_phone_number or ""):
#             updates["business_phone_number"] = formatted_business

#         formatted_personal = format_phone_number(lead.personal_cell_phone, lead.country)
#         if formatted_personal != (lead.personal_cell_phone or ""):
#             updates["personal_cell_phone"] = formatted_personal

#         # 📧 Clean email
#         if lead.email:
#             cleaned_email = clean_text(lead.email)
#             if cleaned_email != lead.email:
#                 updates["email"] = cleaned_email

#         # 🏠 Clean address
#         if lead.address:
#             cleaned_address = clean_text(lead.address)
#             if cleaned_address != lead.address:
#                 updates["address"] = cleaned_address
#                 updates["full_address"] = cleaned_address

#         # 🌆 City, state_code, state cleanup
#         for field in ["city", "state_code", "state"]:
#             val = lead.get(field)
#             if val:
#                 cleaned_val = clean_text(val)
#                 if cleaned_val != val:
#                     updates[field] = cleaned_val

#         # ✅ Save if any changes
#         if updates:
#             frappe.db.set_value("ATM Leads", lead.name, updates)
#             print(f"✅ Updated {lead.name}: {updates}")

#     frappe.db.commit()
#     print("🎯 Patch execution complete.")


####full code clean
# import re
# import frappe

# def extract_digits(phone):
#     return re.sub(r'\D', '', phone or '')

# def format_phone_number(phone, country):
#     digits = extract_digits(phone)
#     if country in ["USA", "Canada"] and len(digits) >= 10:
#         return f"{digits[-10:-7]}-{digits[-7:-4]}-{digits[-4:]}"
#     elif country == "Australia" and len(digits) >= 9:
#         return f"{digits[-9:-6]}-{digits[-6:-3]}-{digits[-3:]}"
#     return phone.strip()

# def clean_text(value):
#     if not value:
#         return ""
#     value = re.sub(r"\s{2,}", " ", value)       # collapse multiple spaces
#     value = re.sub(r"\s*,\s*", ",", value)      # normalize commas
#     value = re.sub(r"[.,:;]+$", "", value.strip())  # remove ending punctuations
#     return value.strip()

# def execute():
#     leads = frappe.get_all("ATM Leads", fields=[
#         "name",
#         "branch",
#         "country",
#         "business_phone_number",
#         "personal_cell_phone",
#         "address",
#         "city",
#         "state",
#         "state_code",
#         "zippostal_code",
#         "email"
#     ])

#     for lead in leads:
#         if lead.country not in ["USA", "Canada", "Australia"]:
#             continue

#         updated_fields = {}

#         # Clean and format phone numbers
#         business_clean = format_phone_number(lead.business_phone_number, lead.country)
#         if business_clean != (lead.business_phone_number or "").strip():
#             updated_fields["business_phone_number"] = business_clean

#         personal_clean = format_phone_number(lead.personal_cell_phone, lead.country)
#         if personal_clean != (lead.personal_cell_phone or "").strip():
#             updated_fields["personal_cell_phone"] = personal_clean

#         # Clean text fields
#         for field in ["address", "city", "state", "state_code", "zippostal_code", "email"]:
#             original = lead.get(field) or ""
#             cleaned = clean_text(original)
#             if cleaned != original.strip():
#                 updated_fields[field] = cleaned

#         if updated_fields:
#             frappe.db.set_value("ATM Leads", lead.name, updated_fields)
#             print(f"✅ Updated {lead.name}: {updated_fields}")

#     frappe.db.commit()
#     print("🎯 Patch execution complete.")


##old
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

