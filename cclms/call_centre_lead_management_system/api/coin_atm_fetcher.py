import requests
from bs4 import BeautifulSoup
import frappe

def fetch_coin_atm_locations():
    url = "https://coinatmradar.com/countries/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    country_sections = soup.find_all('div', class_='list-countries')

    for country_section in country_sections:
        country_name = country_section.find('h2').text
        atms = country_section.find_all('div', class_='list-item')

        for atm in atms:
            location_data = {
                'doctype': 'CoinATMLocation',
                'country': country_name,
                'pin_code': atm.find('span', class_='postal-code').text if atm.find('span', 'postal-code') else '',
                'state': atm.find('span', 'region').text if atm.find('span', 'region') else '',
                'city': atm.find('span', 'locality').text if atm.find('span', 'locality') else '',
                'no_of_locations': atm.find('span', 'locations').text if atm.find('span', 'locations') else '',
                'type_of_coins': atm.find('span', 'coins').text if atm.find('span', 'coins') else '',
                'type_of_operations': atm.find('span', 'operations').text if atm.find('span', 'operations') else '',
                'location_type': atm.find('span', 'location-type').text if atm.find('span', 'location-type') else '',
                'transaction_size': atm.find('span', 'transaction-size').text if atm.find('span', 'transaction-size') else '',
                'latitude': atm['data-lat'] if 'data-lat' in atm.attrs else '',
                'longitude': atm['data-lng'] if 'data-lng' in atm.attrs else '',
            }

            doc = frappe.get_doc(location_data)
            doc.insert()

    frappe.db.commit()

    def run():
    fetch_coin_atm_locations()