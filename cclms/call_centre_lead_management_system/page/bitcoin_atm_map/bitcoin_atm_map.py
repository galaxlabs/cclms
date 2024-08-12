import frappe
from frappe import _

@frappe.whitelist()
def get_atm_locations():
    # Example function to fetch Bitcoin ATM locations
    locations = frappe.get_all('Bitcoin ATM', fields=['name', 'latitude', 'longitude', 'type'])
    return locations

# import frappe
# from frappe import _

# @frappe.whitelist()
# def get_atm_locations():
#     # This function can be called from your JS to get ATM locations
#     locations = frappe.get_all('Bitcoin ATM Location', fields=['latitude', 'longitude', 'name'])
#     return locations
