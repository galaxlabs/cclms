# import re
# import frappe

# def clean_email(email):
#     if not email or email.strip().lower() in ['na', 'n/a', 'none']:
#         return ''

#     email = email.strip().lower().replace(" ", "")
#     email = email.rstrip(".")  # Remove trailing dot

#     # Fix missing dot before TLD (.com, .au, etc.)
#     email = re.sub(
#         r'@([a-z0-9]+)(com|net|org|gov|edu|in|ca|au|pk)(\.com|\.net|\.org|\.gov|\.edu|\.in|\.ca|\.au|\.pk)?$',
#         r'@\1.\2',
#         email
#     )

#     # Remove duplicate .com.com etc.
#     email = re.sub(r'(\.com|\.net|\.org|\.gov|\.edu|\.in|\.ca|\.au|\.pk)+$', lambda m: m.group(1), email)

#     return email

# def clean_text(value):
#     if not value or value.strip().lower() in ['na', 'n/a', 'none']:
#         return ''
#     return re.sub(r'\s{2,}', ' ', value.strip())

# def extract_digits(phone):
#     return re.sub(r'\D', '', phone or '')

# def format_phone_by_country(phone, country):
#     digits = extract_digits(phone)
#     if not digits:
#         return ''

#     if country:
#         country = country.strip().lower()
    
#     # Format for Australia
#     if country == 'australia':
#         if digits.startswith('04') and len(digits) == 10:
#             return f"+61 {digits[1:4]} {digits[4:7]} {digits[7:]}"
#         elif len(digits) == 9 and digits.startswith('4'):
#             return f"+61 {digits[0:3]} {digits[3:6]} {digits[6:]}"
#         else:
#             return digits

#     # Format for US/Canada
#     elif country in ['canada', 'united states', 'usa', 'us']:
#         if len(digits) == 10:
#             return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
#         elif len(digits) == 11 and digits.startswith('1'):
#             return f"{digits[1:4]}-{digits[4:7]}-{digits[7:]}"
#         else:
#             return digits

#     # Return raw digits for unknown countries
#     return digits

# def execute():
#     print("🚀 Running enhanced cleanup patch for ATM Leads...")

#     leads = frappe.get_all("ATM Leads", fields=[
#         "name", "business_phone_number", "personal_cell_phone", "email",
#         "address", "city", "state", "state_code", "zip_code", "country"
#     ])

#     for lead in leads:
#         updated_fields = {}

#         # Phone fields
#         for field in ["business_phone_number", "personal_cell_phone"]:
#             original = lead.get(field)
#             formatted = format_phone_by_country(original, lead.country)
#             if formatted != (original or ""):
#                 updated_fields[field] = formatted
#                 print(f"📞 {field}: '{original}' ➜ '{formatted}'")

#         # Email cleanup
#         email = lead.get("email")
#         cleaned_email = clean_email(email)
#         if cleaned_email != (email or ""):
#             updated_fields["email"] = cleaned_email
#             print(f"📧 email: '{email}' ➜ '{cleaned_email}'")

#         # Address field cleanup
#         for field in ["address", "city", "state", "state_code", "zip_code"]:
#             val = lead.get(field)
#             cleaned = clean_text(val)
#             if cleaned != (val or ""):
#                 updated_fields[field] = cleaned
#                 print(f"🏠 {field}: '{val}' ➜ '{cleaned}'")

#         # Save only if anything changed
#         if updated_fields:
#             frappe.db.set_value("ATM Leads", lead.name, updated_fields)

#     frappe.db.commit()
#     print("✅ All records cleaned and updated successfully.")

# # import re
# # import frappe

# # def clean_email(email):
# #     if not email or email.strip().lower() in ['na', 'n/a', 'none']:
# #         return ''
# #     email = email.replace(" ", "")
# #     if "@" in email and "." not in email.split("@")[1]:
# #         email += ".com"
# #     return email

# # def clean_text(value):
# #     if not value or value.strip().lower() in ['na', 'n/a', 'none']:
# #         return ''
# #     return re.sub(r'\s{2,}', ' ', value.strip())

# # def extract_digits(phone):
# #     return re.sub(r'\D', '', phone or '')

# # def format_phone_by_country(phone, country):
# #     digits = extract_digits(phone or '')
# #     if not digits:
# #         return ''

# #     if country:
# #         country = country.lower()

# #     if country == 'australia':
# #         if digits.startswith('04') and len(digits) == 10:
# #             return f"+61 {digits[1:4]} {digits[4:7]} {digits[7:]}"
# #         elif len(digits) == 9 and digits.startswith('4'):
# #             return f"+61 {digits[0:3]} {digits[3:6]} {digits[6:]}"
# #         else:
# #             return digits
# #     elif country in ['canada', 'united states', 'usa', 'us']:
# #         if len(digits) == 10:
# #             return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
# #         elif len(digits) == 11 and digits.startswith('1'):
# #             return f"{digits[1:4]}-{digits[4:7]}-{digits[7:]}"
# #         else:
# #             return digits
# #     else:
# #         return digits

# # def execute():
# #     print("🚀 Running full cleanup patch for ATM Leads...")

# #     leads = frappe.get_all("ATM Leads", fields=[
# #         "name", "business_phone_number", "personal_cell_phone", "email",
# #         "address", "city", "state", "state_code", "zip_code", "country"
# #     ])

# #     for lead in leads:
# #         updated_fields = {}

# #         # Phone fields
# #         for field in ["business_phone_number", "personal_cell_phone"]:
# #             original = lead.get(field)
# #             formatted = format_phone_by_country(original, lead.country)
# #             if formatted != (original or ""):
# #                 updated_fields[field] = formatted
# #                 print(f"📞 Updated {field}: '{original}' ➜ '{formatted}'")

# #         # Email
# #         email = lead.get("email")
# #         cleaned_email = clean_email(email)
# #         if cleaned_email != (email or ""):
# #             updated_fields["email"] = cleaned_email
# #             print(f"📧 Cleaned email: '{email}' ➜ '{cleaned_email}'")

# #         # Address cleanup
# #         for field in ["address", "city", "state", "state_code", "zip_code"]:
# #             val = lead.get(field)
# #             cleaned = clean_text(val)
# #             if cleaned != (val or ""):
# #                 updated_fields[field] = cleaned
# #                 print(f"📍 Cleaned {field}: '{val}' ➜ '{cleaned}'")

# #         if updated_fields:
# #             frappe.db.set_value("ATM Leads", lead.name, updated_fields)

# #     frappe.db.commit()
# #     print("✅ Done: All lead records processed.")

# # import re
# # import frappe

# # def extract_digits(phone):
# #     return re.sub(r'\D', '', phone or '')

# # def format_phone_number(phone, country):
# #     digits = extract_digits(phone)
# #     if not digits:
# #         return ""
# #     if country in ["USA", "Canada"] and len(digits) >= 10:
# #         return f"{digits[-10:-7]}-{digits[-7:-4]}-{digits[-4:]}"
# #     elif country == "Australia" and len(digits) >= 9:
# #         return f"{digits[-9:-6]}-{digits[-6:-3]}-{digits[-3:]}"
# #     return digits

# # def clean_text(value):
# #     value = (value or "").strip()
# #     value = re.sub(r"[^\w\s\-@]", "", value)  # remove symbols except dash & email @
# #     value = re.sub(r"\s{2,}", " ", value)
# #     return value.strip()

# # def execute():
# #     print("🚀 Running patch to clean ATM Leads...")

# #     leads = frappe.get_all("ATM Leads", fields=[
# #         "name", "country", "business_phone_number", "personal_cell_phone",
# #         "address", "city", "state", "state_code", "zip_code",
# #         "email", "owner_name", "business_name"
# #     ])

# #     for lead in leads:
# #         updated_fields = {}
# #         name = lead.name
# #         country = lead.country or ""

# #         # Clean phone numbers
# #         for field in ["business_phone_number", "personal_cell_phone"]:
# #             original = (lead.get(field) or "").strip()
# #             cleaned = format_phone_number(original, country)
# #             if cleaned and cleaned != original:
# #                 updated_fields[field] = cleaned

# #         # General text fields
# #         for field in ["address", "city", "state", "state_code", "zip_code", "email", "owner_name", "business_name"]:
# #             original = (lead.get(field) or "").strip()
# #             cleaned = clean_text(original)
# #             if cleaned and cleaned.lower() not in ["na", "n/a"] and cleaned != original:
# #                 updated_fields[field] = cleaned

# #         # If address contains full line and city/state are empty, try splitting
# #         if lead.address and not lead.city:
# #             parts = lead.address.split(",")
# #             if len(parts) >= 3:
# #                 updated_fields["address"] = parts[0].strip()
# #                 updated_fields["city"] = parts[1].strip()
# #                 updated_fields["state"] = parts[2].strip()
# #             elif len(parts) == 2:
# #                 updated_fields["address"] = parts[0].strip()
# #                 updated_fields["city"] = parts[1].strip()

# #         if updated_fields:
# #             frappe.db.set_value("ATM Leads", name, updated_fields)
# #             print(f"✅ Updated {name}: {updated_fields}")

# #     frappe.db.commit()
# #     print("🎯 Patch execution complete.")

# # def execute():
# #     print("🚀 Patch is executing!")  # Confirm if it even starts

# # def extract_digits(phone):
# #     return re.sub(r'\D', '', phone or '')

# # def format_phone_number(phone, country):
# #     if not phone:
# #         return ""
# #     digits = extract_digits(phone)
# #     if country in ["USA", "Canada"] and len(digits) >= 10:
# #         return f"{digits[-10:-7]}-{digits[-7:-4]}-{digits[-4:]}"
# #     elif country == "Australia" and len(digits) >= 9:
# #         return f"{digits[-9:-6]}-{digits[-6:-3]}-{digits[-3:]}"
# #     return phone.strip()

# # def clean_text(value):
# #     if not value or value.lower() in ["none", "na", "n/a"]:
# #         return ""
# #     value = value.strip()
# #     value = re.sub(r"\s{2,}", " ", value)
# #     value = re.sub(r"\s*,\s*", ",", value)
# #     value = re.sub(r",+", ",", value)
# #     value = re.sub(r"[.,:;]+$", "", value)
# #     return value.strip()

# # def clean_name(value):
# #     if not value or value.lower() in ["none", "na", "n/a"]:
# #         return ""
# #     value = value.strip()
# #     value = re.sub(r"\s{2,}", " ", value)
# #     value = re.sub(r"[.,:;]+$", "", value)
# #     return value.strip()

# # def split_address_components(address_string):
# #     """Try to split full address into components."""
# #     parts = [p.strip() for p in address_string.split(",") if p.strip()]
# #     parsed = {
# #         "address": "",
# #         "city": "",
# #         "state_code": "",
# #         "zip_code": "",
# #         "country": ""
# #     }

# #     # Minimum expected: street, city, state+zip, country
# #     if len(parts) >= 4:
# #         parsed["address"] = parts[0]
# #         parsed["city"] = parts[1]

# #         # State code and ZIP (e.g., CA 90001)
# #         state_zip = parts[2].split()
# #         if len(state_zip) == 2:
# #             parsed["state_code"] = state_zip[0]
# #             parsed["zip_code"] = state_zip[1]
# #         else:
# #             parsed["state_code"] = parts[2]

# #         parsed["country"] = parts[3]
# #     return parsed

# # def execute():
# #     print("🚀 Running patch to clean and split ATM Leads...")

# #     leads = frappe.get_all("ATM Leads", fields=[
# #         "name", "country", "business_phone_number", "personal_cell_phone",
# #         "address", "city", "state", "state_code", "zip_code", "email",
# #         "owner_name", "business_name"
# #     ])

# #     updated_count = 0

# #     for lead in leads:
# #         country = lead.get("country") or ""
# #         if country not in ["USA", "Canada", "Australia"]:
# #             continue

# #         updated_fields = {}

# #         # Clean & format phones
# #         business_clean = format_phone_number(lead.business_phone_number, country)
# #         if business_clean != (lead.business_phone_number or "").strip():
# #             updated_fields["business_phone_number"] = business_clean

# #         personal_clean = format_phone_number(lead.personal_cell_phone, country)
# #         if personal_clean != (lead.personal_cell_phone or "").strip():
# #             updated_fields["personal_cell_phone"] = personal_clean

# #         # Split full address if other fields are empty
# #         if lead.address and not (lead.city or lead.state_code or lead.zip_code):
# #             parsed = split_address_components(lead.address)
# #             for key in parsed:
# #                 if parsed[key] and not (lead.get(key) or "").strip():
# #                     updated_fields[key] = parsed[key]

# #         # Clean text fields
# #         for field in ["address", "city", "state", "state_code", "zip_code", "email"]:
# #             original = (lead.get(field) or "").strip()
# #             cleaned = clean_text(original)
# #             if cleaned != original:
# #                 updated_fields[field] = cleaned

# #         for field in ["owner_name", "business_name"]:
# #             original = (lead.get(field) or "").strip()
# #             cleaned = clean_name(original)
# #             if cleaned != original:
# #                 updated_fields[field] = cleaned

# #         if updated_fields:
# #             frappe.db.set_value("ATM Leads", lead.name, updated_fields)
# #             print(f"✅ Updated {lead.name}: {updated_fields}")
# #             updated_count += 1

# #     frappe.db.commit()
# #     print(f"🎯 Patch finished. Total updated records: {updated_count}")

    

# # def extract_digits(phone):
# #     return re.sub(r'\D', '', phone or '')

# # def format_phone_number(phone, country):
# #     if not phone:
# #         return ""
# #     digits = extract_digits(phone)
# #     if country in ["USA", "Canada"] and len(digits) >= 10:
# #         return f"{digits[-10:-7]}-{digits[-7:-4]}-{digits[-4:]}"
# #     elif country == "Australia" and len(digits) >= 9:
# #         return f"{digits[-9:-6]}-{digits[-6:-3]}-{digits[-3:]}"
# #     return phone.strip()

# # def clean_text(value):
# #     if not value:
# #         return ""

# #     value = value.strip()

# #     # Convert common invalid entries to empty
# #     if value.lower() in ["none", "na", "n/a"]:
# #         return ""

# #     value = re.sub(r"\s{2,}", " ", value)         # Collapse multiple spaces
# #     value = re.sub(r"\s*,\s*", ",", value)        # Normalize comma spacing
# #     value = re.sub(r",+", ",", value)             # Collapse multiple commas
# #     value = re.sub(r"[.,:;]+$", "", value)        # Remove ending punctuation
# #     return value.strip()

# # def clean_name(value):
# #     if not value:
# #         return ""

# #     value = value.strip()

# #     if value.lower() in ["none", "na", "n/a"]:
# #         return ""

# #     value = re.sub(r"\s{2,}", " ", value)         # Collapse multiple spaces
# #     value = re.sub(r"[.,:;]+$", "", value)        # Remove trailing punctuation
# #     return value.strip()

# # def execute():
# #     print("🚀 Running patch to clean ATM Leads...")

# #     leads = frappe.get_all("ATM Leads", fields=[
# #         "name",
# #         "country",
# #         "business_phone_number",
# #         "personal_cell_phone",
# #         "address",
# #         "city",
# #         "state",
# #         "state_code",
# #         "zip_code",
# #         "email",
# #         "owner_name",
# #         "business_name"
# #     ])

# #     updated_count = 0

# #     for lead in leads:
# #         country = lead.get("country") or ""
# #         if country not in ["USA", "Canada", "Australia"]:
# #             continue

# #         updated_fields = {}

# #         # Phone numbers
# #         business_clean = format_phone_number(lead.business_phone_number, country)
# #         if business_clean != (lead.business_phone_number or "").strip():
# #             updated_fields["business_phone_number"] = business_clean

# #         personal_clean = format_phone_number(lead.personal_cell_phone, country)
# #         if personal_clean != (lead.personal_cell_phone or "").strip():
# #             updated_fields["personal_cell_phone"] = personal_clean

# #         # Text cleanup
# #         text_fields = ["address", "city", "state", "state_code", "zip_code", "email"]
# #         for field in text_fields:
# #             original = (lead.get(field) or "").strip()
# #             cleaned = clean_text(original)
# #             if cleaned != original:
# #                 updated_fields[field] = cleaned

# #         # Name cleanup
# #         name_fields = ["owner_name", "business_name"]
# #         for field in name_fields:
# #             original = (lead.get(field) or "").strip()
# #             cleaned = clean_name(original)
# #             if cleaned != original:
# #                 updated_fields[field] = cleaned

# #         # Apply updates
# #         if updated_fields:
# #             frappe.db.set_value("ATM Leads", lead.name, updated_fields)
# #             print(f"✅ Updated {lead.name}: {updated_fields}")
# #             updated_count += 1

# #     frappe.db.commit()
# #     print(f"🎯 Patch execution complete. Total updated records: {updated_count}")



# # import re
# # import frappe

# # ALLOWED_COUNTRIES = ["USA", "Canada", "Australia"]

# # def format_phone_number(phone, country):
# #     phone = re.sub(r"\D", "", phone or "")
# #     if country in ["USA", "Canada"] and len(phone) >= 10:
# #         return f"{phone[-10:-7]}-{phone[-7:-4]}-{phone[-4:]}"
# #     elif country == "Australia" and len(phone) >= 9:
# #         return f"{phone[-9:-6]}-{phone[-6:-3]}-{phone[-3:]}"
# #     return phone

# # def clean_text(value):
# #     if not value:
# #         return ''
# #     value = re.sub(r"\s{2,}", " ", value)  # Collapse multiple spaces
# #     value = re.sub(r",+", ",", value)      # Replace multiple commas
# #     value = re.sub(r"[.,:;]+$", "", value.strip())  # Remove trailing punctuation
# #     return value.strip()

# # def execute():
# #     leads = frappe.get_all("ATM Leads", fields=[
# #         "name",
# #         "branch",
# #         "country",
# #         "business_phone_number",
# #         "personal_cell_phone",
# #         "email",
# #         "address",
# #         "full_address",
# #         "city",
# #         "state_code",
# #         "state"
# #     ])

# #     for lead in leads:
# #         if lead.branch != "Karachi" or lead.country not in ALLOWED_COUNTRIES:
# #             continue

# #         updates = {}

# #         # 📞 Phone formatting
# #         formatted_business = format_phone_number(lead.business_phone_number, lead.country)
# #         if formatted_business != (lead.business_phone_number or ""):
# #             updates["business_phone_number"] = formatted_business

# #         formatted_personal = format_phone_number(lead.personal_cell_phone, lead.country)
# #         if formatted_personal != (lead.personal_cell_phone or ""):
# #             updates["personal_cell_phone"] = formatted_personal

# #         # 📧 Clean email
# #         if lead.email:
# #             cleaned_email = clean_text(lead.email)
# #             if cleaned_email != lead.email:
# #                 updates["email"] = cleaned_email

# #         # 🏠 Clean address
# #         if lead.address:
# #             cleaned_address = clean_text(lead.address)
# #             if cleaned_address != lead.address:
# #                 updates["address"] = cleaned_address
# #                 updates["full_address"] = cleaned_address

# #         # 🌆 City, state_code, state cleanup
# #         for field in ["city", "state_code", "state"]:
# #             val = lead.get(field)
# #             if val:
# #                 cleaned_val = clean_text(val)
# #                 if cleaned_val != val:
# #                     updates[field] = cleaned_val

# #         # ✅ Save if any changes
# #         if updates:
# #             frappe.db.set_value("ATM Leads", lead.name, updates)
# #             print(f"✅ Updated {lead.name}: {updates}")

# #     frappe.db.commit()
# #     print("🎯 Patch execution complete.")


# ####full code clean
# # import re
# # import frappe

# # def extract_digits(phone):
# #     return re.sub(r'\D', '', phone or '')

# # def format_phone_number(phone, country):
# #     digits = extract_digits(phone)
# #     if country in ["USA", "Canada"] and len(digits) >= 10:
# #         return f"{digits[-10:-7]}-{digits[-7:-4]}-{digits[-4:]}"
# #     elif country == "Australia" and len(digits) >= 9:
# #         return f"{digits[-9:-6]}-{digits[-6:-3]}-{digits[-3:]}"
# #     return phone.strip()

# # def clean_text(value):
# #     if not value:
# #         return ""
# #     value = re.sub(r"\s{2,}", " ", value)       # collapse multiple spaces
# #     value = re.sub(r"\s*,\s*", ",", value)      # normalize commas
# #     value = re.sub(r"[.,:;]+$", "", value.strip())  # remove ending punctuations
# #     return value.strip()

# # def execute():
# #     leads = frappe.get_all("ATM Leads", fields=[
# #         "name",
# #         "branch",
# #         "country",
# #         "business_phone_number",
# #         "personal_cell_phone",
# #         "address",
# #         "city",
# #         "state",
# #         "state_code",
# #         "zip_code",
# #         "email"
# #     ])

# #     for lead in leads:
# #         if lead.country not in ["USA", "Canada", "Australia"]:
# #             continue

# #         updated_fields = {}

# #         # Clean and format phone numbers
# #         business_clean = format_phone_number(lead.business_phone_number, lead.country)
# #         if business_clean != (lead.business_phone_number or "").strip():
# #             updated_fields["business_phone_number"] = business_clean

# #         personal_clean = format_phone_number(lead.personal_cell_phone, lead.country)
# #         if personal_clean != (lead.personal_cell_phone or "").strip():
# #             updated_fields["personal_cell_phone"] = personal_clean

# #         # Clean text fields
# #         for field in ["address", "city", "state", "state_code", "zip_code", "email"]:
# #             original = lead.get(field) or ""
# #             cleaned = clean_text(original)
# #             if cleaned != original.strip():
# #                 updated_fields[field] = cleaned

# #         if updated_fields:
# #             frappe.db.set_value("ATM Leads", lead.name, updated_fields)
# #             print(f"✅ Updated {lead.name}: {updated_fields}")

# #     frappe.db.commit()
# #     print("🎯 Patch execution complete.")


# ##old
# # import re
# # import frappe

# # def extract_digits(phone):
# #     return re.sub(r'\D', '', phone or '')

# # def format_to_us_number(phone):
# #     digits = extract_digits(phone)
# #     if len(digits) == 10:
# #         return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
# #     else:
# #         print(f"⚠️ Skipping invalid: '{phone}' ➜ digits: '{digits}' (length: {len(digits)})")
# #         return phone

# # # ✅ Required for Frappe to run this patch
# # def execute():
# #     leads = frappe.get_all("ATM Leads", fields=["name", "business_phone_number", "personal_cell_phone"])
# #     for lead in leads:
# #         updated = False

# #         new_business = format_to_us_number(lead.business_phone_number)
# #         new_personal = format_to_us_number(lead.personal_cell_phone)

# #         if new_business != lead.business_phone_number:
# #             frappe.db.set_value("ATM Leads", lead.name, "business_phone_number", new_business)
# #             updated = True
# #             print(f"✅ Updated business phone: {lead.business_phone_number} ➜ {new_business}")

# #         if new_personal != lead.personal_cell_phone:
# #             frappe.db.set_value("ATM Leads", lead.name, "personal_cell_phone", new_personal)
# #             updated = True
# #             print(f"✅ Updated personal phone: {lead.personal_cell_phone} ➜ {new_personal}")

# #         if updated:
# #             frappe.db.commit()

