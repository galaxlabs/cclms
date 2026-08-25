import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate
from frappe.utils.data import date_diff

TRANSITIONS = {
	"Pending Review": {
		"actions": {
			"approve": {"to": "Approved"},
			"reject": {"to": "Rejected"},
		},
	},
	"Approved": {
		"actions": {
			"reject": {"to": "Rejected"},
		},
	},
	"Signed": {
		"actions": {
			"install": {"to": "Installed"},
			"reject": {"to": "Signed Rejected"},
		},
	},
	"Installed": {
		"actions": {},
	},
	"Rejected": {
		"actions": {
			"approve": {"to": "Approved"},
		},
	},
}

WORKFLOW_TO_PORTAL = {
	"Pending": "Pending Review",
	"Approved": "Approved",
	"Rejected": "Rejected",
	"Signed": "Signed",
	"Signed Rejected": "Signed Rejected",
	"Installed": "Installed",
	"Converted": "Converted",
}
PORTAL_TO_WORKFLOW = {portal: workflow for workflow, portal in WORKFLOW_TO_PORTAL.items()}
PORTAL_DATA_START_DATE = "2025-08-07"


def _get_user_companies():
	if frappe.session.user == "Guest":
		frappe.throw("Authentication required", frappe.PermissionError)
	profile = frappe.db.get_value(
		"Portal Profile", {"user": frappe.session.user, "enabled": 1}, ["name", "company"], as_dict=True
	)
	if not profile:
		frappe.throw("Portal access is not enabled for this user", frappe.PermissionError)
	companies = [profile.company] if profile.company else []
	companies.extend(
		frappe.get_all("Portal Profile Company", filters={"parent": profile.name}, pluck="company")
	)
	active_companies = frappe.get_all(
		"Operator Companies", filters={"name": ["in", list(set(companies))], "active": 1}, pluck="name"
	)
	if not active_companies:
		frappe.throw("No active operator company is assigned to this portal user", frappe.PermissionError)
	return active_companies


def _get_user_company():
	return _get_user_companies()[0]


def _location_filters(companies, status=None):
	filters = [
		["company", "in", companies],
		["workflow_state", "in", list(WORKFLOW_TO_PORTAL)],
		["post_date", ">=", PORTAL_DATA_START_DATE],
		["modified", ">=", PORTAL_DATA_START_DATE],
	]
	if status:
		workflow_state = PORTAL_TO_WORKFLOW.get(status)
		if not workflow_state:
			frappe.throw("Unsupported location status.")
		filters.append(["workflow_state", "=", workflow_state])
	return filters


def _within_cutoff(row):
	# Cut date is based on post_date; modified only applies to records that
	# already have post_date >= cut (bulk reconciliation touched modified on all).
	from frappe.utils import getdate
	if not row.get("post_date"):
		return False
	return getdate(row.get("post_date")) >= getdate(PORTAL_DATA_START_DATE) and getdate(row.get("modified")) >= getdate(PORTAL_DATA_START_DATE)


def _state_matches(rule, state, state_code):
	return (
		str(rule.get("state") or "").strip().casefold() == str(state or "").strip().casefold()
		or str(rule.get("state_code") or "").strip().casefold() == str(state_code or "").strip().casefold()
	)


def _company_allows_state(company, state, state_code):
	company_doc = frappe.get_cached_doc("Operator Companies", company)
	permitted = company_doc.get("state_name") or []
	if permitted:
		return any(_state_matches(rule, state, state_code) for rule in permitted)
	restricted = company_doc.get("restricted_states") or []
	return not any(_state_matches(rule, state, state_code) for rule in restricted)


def _company_allows_business_type(company, business_type):
	company_doc = frappe.get_cached_doc("Operator Companies", company)
	restricted_types = {row.restricted_business for row in company_doc.get("restricted_type") or []}
	return business_type not in restricted_types


def _can_access_location(doc, companies):
	return (
		doc.company in companies
		and _company_allows_state(doc.company, doc.state, doc.state_code)
		and _company_allows_business_type(doc.company, doc.business_type)
	)


def _portal_location(row):
	row["status"] = WORKFLOW_TO_PORTAL.get(row.pop("workflow_state", None))
	return row


LOCATION_FIELDS = [
	"name", "business_name", "business_type", "full_address", "city", "state", "state_code",
	"zip_code", "company", "workflow_state", "post_date", "approve_date", "sign_date", "install_date", "creation", "modified",
	"reject_reason", "reject_reason_other",
]

LOCATION_DATE_FIELDS = {"post_date", "approve_date", "sign_date", "install_date", "creation"}

LOCATION_DETAIL_FIELDS = [
	*LOCATION_FIELDS, "latitude", "longitude", "notes",
]


@frappe.whitelist(allow_guest=True)
def get_portal_config():
	user = frappe.session.user
	if user == "Guest":
		return {
			"branding": {
				"brand_name": "Xperts Global CRM",
				"brand_subtitle": "Location Intelligence",
				"logo": None,
				"primary_color": "#1F1F25",
				"secondary_color": "#0D0D0D",
			},
			"available_pages": [],
		}

	companies = _get_user_companies()
	company = companies[0]
	is_manager = "System Manager" in frappe.get_roles(user)
	profile = frappe.db.get_value("Portal Profile", {"user": user, "enabled": 1},
		["company", "role_type"], as_dict=True)

	branding = _get_branding(company)
	available_pages = ["dashboard", "locations", "settings", "profile"]
	if is_manager:
		available_pages.extend(["users", "productivity"])

	return {
		"branding": branding,
		"available_pages": available_pages,
		"company": company,
		"companies": companies,
		"role_type": profile.get("role_type") if profile else "Portal User",
		"is_manager": is_manager,
		"dashboard_method": "cclms.api.portal.get_dashboard",
		"reject_reason_options": get_reject_reason_options(),
	}


def get_reject_reason_options():
	return frappe.get_meta("ATM Leads").get_field("reject_reason").options.split("\n")


def _get_branding(company_name):
	if company_name and frappe.db.exists("Operator Companies", company_name):
		doc = frappe.get_doc("Operator Companies", company_name)
		return {
			"brand_name": doc.get("operator_name") or "Xperts Global CRM",
			"brand_subtitle": "Location Intelligence",
			"logo": None,
			"primary_color": "#1F1F25",
			"secondary_color": "#0D0D0D",
		}
	return {
		"brand_name": "Xperts Global CRM",
		"brand_subtitle": "Location Intelligence",
		"logo": doc.get("logo"),
		"primary_color": "#1F1F25",
		"secondary_color": "#0D0D0D",
	}


@frappe.whitelist()
def get_company_profile():
	company = _get_user_company()
	return frappe.db.get_value(
		"Operator Companies",
		company,
		["name", "operator_name", "logo", "contact_name", "contact_email", "contact_phone", "website", "business_address"],
		as_dict=True,
	)


@frappe.whitelist()
def update_company_profile(data: dict):
	company = _get_user_company()
	allowed = {"contact_name", "contact_email", "contact_phone", "website", "business_address"}
	updates = {field: value for field, value in data.items() if field in allowed}
	if not updates:
		frappe.throw("No valid business fields provided.")
	frappe.db.set_value("Operator Companies", company, updates, update_modified=True)
	frappe.clear_cache(doctype="Operator Companies")
	return get_company_profile()


@frappe.whitelist()
def get_dashboard(range_days: str = "30"):
	companies = _get_user_companies()
	filters = _location_filters(companies)

	all_leads = frappe.get_all("ATM Leads", fields=["workflow_state", "company", "state", "state_code", "business_type", "city", "zip_code", "post_date"], filters=filters, limit_page_length=100000)
	status_counts = {}
	city_stats = {}
	zip_stats = {}
	region_stats = {}
	timeseries = {}
	range_days = int(range_days or 30)
	from_date = getdate(add_days(nowdate(), -(range_days - 1)))
	for l in all_leads:
		if not _can_access_location(l, companies):
			continue
		status = WORKFLOW_TO_PORTAL[l["workflow_state"]]
		status_counts[status] = status_counts.get(status, 0) + 1
		for key, value in (("city", l.city), ("zip_code", l.zip_code), ("region", l.state)):
			if not value:
				continue
			bucket = city_stats if key == "city" else zip_stats if key == "zip_code" else region_stats
			entry = bucket.setdefault(value, {"label": value, "total": 0, "signed": 0, "installed": 0})
			entry["total"] += 1
			entry["signed"] += int(status == "Signed")
			entry["installed"] += int(status == "Installed")
		post = getdate(l.post_date) if l.post_date else getdate(l.creation)
		if post < from_date:
			continue
		day_key = post.strftime("%Y-%m-%d")
		bucket = timeseries.setdefault(day_key, {"date": day_key, "total": 0, "signed": 0, "installed": 0, "approved": 0, "rejected": 0, "pending": 0, "signed_rejected": 0})
		bucket["total"] += 1
		if status == "Signed":
			bucket["signed"] += 1
		elif status == "Installed":
			bucket["installed"] += 1
		elif status == "Approved":
			bucket["approved"] += 1
		elif status == "Rejected":
			bucket["rejected"] += 1
		elif status == "Pending Review":
			bucket["pending"] += 1
		elif status == "Signed Rejected":
			bucket["signed_rejected"] += 1

	recent = frappe.get_all("ATM Leads",
		fields=LOCATION_FIELDS,
		filters=filters,
		order_by="creation desc",
		limit=100,
	)

	return {
		"counts": {
		"total": sum(status_counts.values()),
			"by_status": status_counts,
		},
		"recent": [_portal_location(row) for row in recent if _can_access_location(row, companies)][:10],
		"city_stats": sorted(city_stats.values(), key=lambda item: item["total"], reverse=True)[:8],
		"zip_stats": sorted(zip_stats.values(), key=lambda item: item["total"], reverse=True)[:8],
		"region_stats": sorted(region_stats.values(), key=lambda item: item["total"], reverse=True)[:8],
		"timeseries": sorted(timeseries.values(), key=lambda item: item["date"]),
	}


@frappe.whitelist()
def sync_locations(since: str = None):
	companies = _get_user_companies()
	if since:
		filters = _location_filters(companies)
		filters.append(["modified", ">", since])
	else:
		filters = _location_filters(companies)
	rows = frappe.get_all("ATM Leads", fields=LOCATION_FIELDS, filters=filters, order_by="creation desc", limit_page_length=100000)
	allowed = []
	removed = []
	for row in rows:
		if row.workflow_state in WORKFLOW_TO_PORTAL and _within_cutoff(row) and _can_access_location(row, companies):
			allowed.append(_portal_location(row))
		else:
			removed.append(row.name)
	return {"rows": allowed, "removed": removed, "synced_at": now_datetime().strftime("%Y-%m-%d %H:%M:%S.%f")}


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
	companies = _get_user_companies()
	date_field = date_field or "post_date"
	if date_field not in LOCATION_DATE_FIELDS:
		frappe.throw("Unsupported date filter.")

	filters = _location_filters(companies, status)
	if from_date:
		filters.append([date_field, ">=", f"{from_date} 00:00:00" if date_field == "creation" else from_date])
	if to_date:
		filters.append([date_field, "<=", f"{to_date} 23:59:59.999999" if date_field == "creation" else to_date])

	rows = frappe.get_all("ATM Leads",
		fields=LOCATION_FIELDS,
		filters=filters,
		order_by="creation desc",
		limit_page_length=100000,
	)
	rows = [row for row in rows if _can_access_location(row, companies)]
	filter_options = {
		"cities": sorted({row.city for row in rows if row.city}),
		"states": sorted({row.state for row in rows if row.state}),
		"zip_codes": sorted({row.zip_code for row in rows if row.zip_code}),
		"business_types": sorted({row.business_type for row in rows if row.business_type}),
	}
	if city:
		rows = [row for row in rows if row.city == city]
	if state:
		rows = [row for row in rows if row.state == state]
	if zip_code:
		rows = [row for row in rows if row.zip_code == zip_code]
	if business_type:
		rows = [row for row in rows if row.business_type == business_type]
	if search:
		query = search.strip().casefold()
		rows = [
			row for row in rows
			if all(
				term in " ".join(
					str(row.get(field) or "")
					for field in ("business_name", "business_type", "full_address", "city", "state", "state_code", "zip_code")
				).casefold()
				for term in query.split()
			)
		]
	page_size = min(max(int(page_size), 10), 1000)
	page = max(int(page), 1)
	page_count = max(1, (len(rows) + page_size - 1) // page_size)
	page = min(page, page_count)
	start = (page - 1) * page_size
	return {
		"rows": [_portal_location(row) for row in rows[start:start + page_size]],
		"total": len(rows),
		"page": page,
		"page_size": page_size,
		"page_count": page_count,
		"filter_options": filter_options,
		"date_field": date_field,
		"order_by": "creation desc",
	}


@frappe.whitelist()
def get_location(name: str):
	companies = _get_user_companies()
	doc = frappe.get_doc("ATM Leads", name)
	if not _can_access_location(doc, companies):
		frappe.throw("Not permitted", frappe.PermissionError)
	data = {field: doc.get(field) for field in LOCATION_DETAIL_FIELDS}
	return _portal_location(data)


@frappe.whitelist()
def update_location(name: str, data: dict):
	companies = _get_user_companies()
	doc = frappe.get_doc("ATM Leads", name)
	if not _can_access_location(doc, companies):
		frappe.throw("Not permitted", frappe.PermissionError)
	allowed = {"business_name", "business_type", "full_address", "city", "state", "zip_code", "notes", "reject_reason", "reject_reason_other"}
	changed = False
	for key, value in data.items():
		if key in allowed and value is not None:
			setattr(doc, key, value)
			changed = True
	if not changed:
		frappe.throw("No valid fields provided.")
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def create_location(data: dict):
	companies = _get_user_companies()
	company = data.get("company") or companies[0]
	if company not in companies:
		frappe.throw("Not permitted", frappe.PermissionError)
	if not _company_allows_state(company, data.get("state"), data.get("state_code")):
		frappe.throw("This state is not available for the selected operator company", frappe.PermissionError)
	if not _company_allows_business_type(company, data.get("business_type")):
		frappe.throw("This business type is restricted for the selected operator company", frappe.PermissionError)
	allowed = {"business_name", "business_type", "full_address", "city", "state", "state_code", "zip_code", "notes"}
	doc = frappe.get_doc({"doctype": "ATM Leads", "company": company, **{key: value for key, value in data.items() if key in allowed}})
	doc.insert(ignore_permissions=True)
	return _portal_location(doc.as_dict())


@frappe.whitelist()
def execute_action(doctype: str, name: str, action: str, install_date: str = None, reject_reason: str = None, reject_reason_other: str = None):
	if doctype not in {"ATM Lead", "ATM Leads"}:
		frappe.throw("Unsupported doctype.")
	companies = _get_user_companies()
	doc = frappe.get_doc("ATM Leads", name)
	if not _can_access_location(doc, companies):
		frappe.throw("Not permitted", frappe.PermissionError)

	current = WORKFLOW_TO_PORTAL.get(doc.workflow_state)
	config = TRANSITIONS.get(current)
	if not config or action not in config.get("actions", {}):
		frappe.throw(f"Action '{action}' not available from status '{current}'")

	action_def = config["actions"][action]
	updates = {"workflow_state": action_def["to"]}
	if action == "install":
		if not install_date:
			frappe.throw("An installation date is required.")
		updates["install_date"] = install_date
	# Stamp the milestone action date (approve/sign/reject/convert/install)
	_milestone_date_map = {
		"Approved": "approve_date",
		"Signed": "sign_date",
		"Signed Rejected": "sign_rejected",
		"Converted": "convert_date",
		"Installed": "install_date",
		"installed/Removed": "remove_date",
	}
	_date_field = _milestone_date_map.get(action_def["to"])
	if _date_field and _date_field not in updates and not doc.get(_date_field):
		updates[_date_field] = now_datetime().strftime("%Y-%m-%d")
	if action in {"reject", "approve"} and action_def.get("to") in {"Rejected", "Signed Rejected"}:
		if reject_reason:
			updates["reject_reason"] = reject_reason
		if reject_reason == "Other" and reject_reason_other:
			updates["reject_reason_other"] = reject_reason_other
	# Desk permissions do not grant Portal User access to ATM Leads. The company
	# check above is the authorization boundary for this purpose-built portal API.
	frappe.db.set_value("ATM Leads", doc.name, updates, update_modified=True)
	frappe.db.commit()
	return {"name": doc.name, "status": WORKFLOW_TO_PORTAL[action_def["to"]], "message": "Installation scheduled" if action == "install" else "Location updated"}
