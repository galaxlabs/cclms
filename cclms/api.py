import frappe
import requests

@frappe.whitelist()
def search_location(query):
    # Example: Dummy data for testing purposes
    # Replace this with actual search logic (e.g., querying a database or an external API)
    locations = [
        {"lat": "51.505", "lon": "-0.09", "display_name": "Example Location 1"},
        {"lat": "40.7128", "lon": "-74.0060", "display_name": "Example Location 2"}
    ]
    
    # Filter based on the query
    result = [location for location in locations if query.lower() in location["display_name"].lower()]
    
    return result if result else []


# @frappe.whitelist()
# def search_location(query):
#     url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}"
#     response = requests.get(url)

#     if response.status_code == 200:
#         return response.json()
#     else:
#         frappe.throw("Failed to fetch location data")
