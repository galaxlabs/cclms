import frappe
from cclms.call_centre_lead_management_system.api.coin_atm_fetcher import fetch_coin_atm_locations

@frappe.whitelist()
def run_coin_atm_fetcher():
    fetch_coin_atm_locations()
