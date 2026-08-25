import importlib

import frappe
from cclms.api import portal


def _portal():
	return importlib.reload(portal)


@frappe.whitelist(allow_guest=True)
def get_portal_config():
	return _portal().get_portal_config()


@frappe.whitelist()
def get_dashboard(range_days: str = "30"):
	return _portal().get_dashboard(range_days)


@frappe.whitelist()
def list_locations(
	page: int = 1,
	page_size: int = 25,
	status: str = None,
	search: str = None,
	from_date: str = None,
	to_date: str = None,
	date_field: str = "post_date",
	city: str = None,
	state: str = None,
	zip_code: str = None,
	business_type: str = None,
):
	return _portal().list_locations(
		page, page_size, status, search, from_date, to_date,
		date_field, city, state, zip_code, business_type,
	)


@frappe.whitelist()
def get_location(name: str):
	return _portal().get_location(name)


@frappe.whitelist()
def update_location(name: str, data: dict):
	return _portal().update_location(name, data)


@frappe.whitelist()
def execute_action(doctype: str, name: str, action: str, install_date: str = None, reject_reason: str = None, reject_reason_other: str = None):
	return _portal().execute_action(doctype, name, action, install_date, reject_reason, reject_reason_other)
