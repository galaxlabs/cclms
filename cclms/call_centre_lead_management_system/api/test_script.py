import frappe

from cclms.call_centre_lead_management_system.api.coin_atm_fetcher import fetch_coin_atm_locations

# if __name__ == "__main__":
#     frappe.connect(site='ccmerp')  # Replace with your site name
#     fetch_coin_atm_locations()
#     frappe.db.commit()

def run():
    fetch_coin_atm_locations()