# In cclms/call_centre_lead_management_system/doctype/atm_locations/atm_locations.py

# Copyright (c) 2025, Galaxy and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe.utils import now
from frappe.model.document import Document

class ATMLocations(Document):
	pass

# @frappe.whitelist()
# def fetch_and_store_locations(search_type, latitude, longitude, radius=5000):
# """
# Fetches data from Google Maps and stores it in ATM Locations Doctype.

# Args:
# 	search_type (str): The type of place to search (e.g., gas_station, convenience_store).
# 	latitude (float): Latitude of the search location.
# 	longitude (float): Longitude of the search location.
# 	radius (int): Search radius in meters (default is 5000m).

# Returns:
# 	dict: Summary of the operation.
# """
# # Get the Google API key from site config
# api_key = frappe.conf.get("google_maps_api_key")
# if not api_key:
# 	frappe.throw("Google Maps API key is not configured in site config.")

# # Define the Places API endpoint
# endpoint = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# # Parameters for the API request
# params = {
# 	"key": api_key,
# 	"location": f"{latitude},{longitude}",
# 	"radius": radius,
# 	"type": search_type
# }

# # Make the API request
# response = requests.get(endpoint, params=params)
# if response.status_code != 200:
# 	frappe.throw(f"Failed to fetch data from Google Maps: {response.status_code}")

# # Parse the response
# results = response.json().get("results", [])
# if not results:
# 	return {"message": "No locations found."}

# # Loop through results and store in ATM Locations Doctype
# added_records = 0
# for place in results:
# 	try:
# 		# Extract relevant fields
# 		business_name = place.get("name")
# 		address = place.get("vicinity")
# 		location = place.get("geometry", {}).get("location", {})
# 		latitude = location.get("lat")
# 		longitude = location.get("lng")
		
# 		# Check for duplicates
# 		if frappe.db.exists("ATM Locations", {"latitude": latitude, "longitude": longitude}):
# 			continue
		
# 		# Create a new record
# 		new_doc = frappe.get_doc({
# 			"doctype": "ATM Locations",
# 			"business_name": business_name,
# 			"address": address,
# 			"latitude": latitude,
# 			"longitude": longitude,
# 			"other_metadata": frappe.as_json(place),
# 			"creation": now()
# 		})
# 		new_doc.insert(ignore_permissions=True)
# 		added_records += 1
	
# 	except Exception as e:
# 		frappe.log_error(message=str(e), title="Error Saving ATM Location")

# return {"message": f"{added_records} locations added successfully."}
