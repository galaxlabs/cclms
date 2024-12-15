# cclms/api.py

import frappe
from frappe import _
import requests
from bs4 import BeautifulSoup
from frappe.utils import now_datetime

# @frappe.whitelist()
# def search_location(query):
#     url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}"
#     response = requests.get(url)

#     if response.status_code == 200:
#         return response.json()
#     else:
#         frappe.throw("Failed to fetch location data")
