import json
import re
from urllib.parse import urlencode

import frappe
import requests
from frappe.utils import get_url, now_datetime

from cclms.api.atm_lead_helper import lookup_existing_lead
from cclms.api.competitor_kiosk_helper import _existing_competitor, _normalize_zip, upsert_competitor_kiosk_from_radar
from cclms.services.zipintel.intelligence import (
    _competitor_rows_for_zip,
    _lead_rows_for_zip,
    _nearest_distance,
    generate_zip_ai_hint,
)

US_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}
US_STATE_CODES = {name.upper(): code for code, name in US_STATE_NAMES.items()}


def _payload(payload=None, **kwargs):
    if isinstance(payload, dict):
        data = dict(payload)
    elif payload:
        data = json.loads(payload)
    else:
        data = {}
    data.update({key: value for key, value in kwargs.items() if value is not None})
    return data


def _clip(value, length=140):
    if value in (None, ""):
        return value
    return str(value)[:length]


def _clean_map_text(value):
    if value in (None, ""):
        return ""
    text = str(value)
    text = text.replace("\ufeff", "")
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e]", "", text)
    text = re.sub(r"^[^\w#(]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,")


def _state_code(value):
    text = _clean_map_text(value).upper()
    if not text:
        return ""
    if text in US_STATE_NAMES:
        return text
    return US_STATE_CODES.get(text, text if len(text) <= 3 else "")


def _state_name(value):
    code = _state_code(value)
    if code in US_STATE_NAMES:
        return US_STATE_NAMES[code]
    return _clean_map_text(value)


def _address_parts(address):
    clean = _clean_map_text(address)
    if not clean:
        return {"address": "", "city": "", "state": "", "state_code": "", "zip_code": "", "country": ""}

    parts = [part.strip() for part in clean.split(",") if part.strip()]
    country = ""
    if parts and parts[-1].lower() in {"united states", "usa", "us"}:
        country = "United States"
        parts = parts[:-1]
    first_line = parts[0] if parts else clean
    city = parts[-2] if len(parts) >= 2 else ""
    tail = parts[-1] if parts else ""
    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", tail) or re.search(r"\b(\d{5})(?:-\d{4})?\b", clean)
    zip_code = zip_match.group(1) if zip_match else ""
    state_code = ""
    state_name = ""
    state_match = re.search(r"\b([A-Z]{2})\b", tail)
    if state_match:
        state_code = _state_code(state_match.group(1))
        state_name = _state_name(state_code)
    return {
        "address": first_line,
        "city": _clean_map_text(city),
        "state": state_name,
        "state_code": state_code,
        "zip_code": zip_code,
        "country": country,
    }


def _compose_full_address(parts):
    values = [
        parts.get("address"),
        parts.get("city"),
        parts.get("state_code") or parts.get("state"),
        parts.get("zip_code"),
        parts.get("country"),
    ]
    return ", ".join([_clean_map_text(value) for value in values if _clean_map_text(value)])


def _normalize_opening_hours(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (list, tuple)):
        lines = [_clean_map_text(item) for item in value if _clean_map_text(item)]
    else:
        text = str(value).replace("\r\n", "\n")
        lines = [_clean_map_text(item) for item in text.split("\n") if _clean_map_text(item)]
    return "\n".join(lines)


def _normalize_opening_time_token(value):
    text = _clean_map_text(value)
    text = text.replace("\u202f", " ").replace("\xa0", " ")
    text = re.sub(r"(?i)\b(am|pm)\b", lambda match: match.group(1).upper(), text)
    text = re.sub(r"(?i)(\d)(am|pm)\b", r"\1 \2", text)
    text = re.sub(r"(?i)\b(am|pm)(\d)", r"\1 \2", text)
    return text.strip()


def _extract_opening_time_range(value):
    text = _normalize_opening_time_token(value)
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"(?i)\bto\b", "-", text)
    match = re.search(
        r"(\d{1,2}(?::\d{2})?\s*[AP]M)\s*-\s*(\d{1,2}(?::\d{2})?\s*[AP]M)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None, None
    return _normalize_opening_time_token(match.group(1)), _normalize_opening_time_token(match.group(2))


def _opening_hours_rows(value):
    normalized = _normalize_opening_hours(value)
    if not normalized:
        return []

    weekday_pattern = re.compile(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?=\s|\d)",
        re.IGNORECASE,
    )
    rows = []
    pending_weekday = ""
    for raw_line in normalized.split("\n"):
        line = _clean_map_text(raw_line)
        if not line:
            continue
        match = weekday_pattern.match(line)
        if match:
            weekday = match.group(1).title()
            remainder = line[match.end():].strip(" :-")
            if not remainder:
                pending_weekday = weekday
                continue
            opening_time, closing_time = _extract_opening_time_range(remainder)
            if opening_time and closing_time:
                rows.append(
                    {
                        "weekday": weekday,
                        "opening_time": opening_time,
                        "closing_time": closing_time,
                    }
                )
            pending_weekday = ""
            continue

        if not pending_weekday:
            continue

        if "closed" in line.lower():
            pending_weekday = ""
            continue

        opening_time, closing_time = _extract_opening_time_range(line)
        if not opening_time or not closing_time:
            continue
        rows.append(
            {
                "weekday": pending_weekday,
                "opening_time": opening_time,
                "closing_time": closing_time,
            }
        )
        pending_weekday = ""
    return rows


def _map_business_type(value):
    category = _clean_map_text(value)
    if not category or not frappe.db.exists("DocType", "Business Types"):
        return ""

    rows = frappe.get_all("Business Types", fields=["name"], order_by="name asc", limit_page_length=0)
    names = [(row.get("name") or "").strip() for row in rows if (row.get("name") or "").strip()]
    lowered = {name.lower(): name for name in names}
    if category.lower() in lowered:
        return lowered[category.lower()]

    normalized_category = re.sub(r"[^a-z0-9]+", " ", category.lower()).strip()
    category_tokens = set(normalized_category.split())
    if not category_tokens:
        return ""

    best_name = ""
    best_score = 0
    for name in names:
        normalized_name = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
        name_tokens = set(normalized_name.split())
        if not name_tokens:
            continue
        if normalized_name in normalized_category or normalized_category in normalized_name:
            score = len(name_tokens) + 10
        else:
            score = len(category_tokens & name_tokens)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name if best_score > 0 else ""


def _request_context(payload=None, **kwargs):
    data = _payload(payload, **kwargs)
    place = data.get("place") or {}
    coordinates = place.get("coordinates") or {}
    merged = {
        "device_id": data.get("device_id"),
        "employee": data.get("employee"),
        "source_system": data.get("source_system"),
        "browser_context": data.get("browser_context") or {},
        "page_context": data.get("page_context") or {},
    }
    merged.update(place)
    if coordinates.get("lat") is not None and merged.get("latitude") in (None, ""):
        merged["latitude"] = coordinates.get("lat")
    if coordinates.get("lng") is not None and merged.get("longitude") in (None, ""):
        merged["longitude"] = coordinates.get("lng")
    return merged


def _meta_fields(doctype, candidates):
    meta = frappe.get_meta(doctype)
    available = {field.fieldname for field in meta.fields}
    available.update({"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"})
    return [field for field in candidates if field in available]


def _db_fields(doctype, candidates):
    table_name = f"tab{doctype}"
    try:
        columns = set(frappe.db.get_table_columns(table_name) or [])
    except Exception:
        columns = set()
    return [field for field in candidates if field == "name" or field in columns]


def _crm_base_url():
    return (get_url() or "").rstrip("/")


def _google_maps_key():
    try:
        return frappe.db.get_single_value("Google Maps Settings", "api_key") or frappe.conf.get("google_maps_api_key")
    except Exception:
        return frappe.conf.get("google_maps_api_key")


def _reverse_geocode_parts(latitude=None, longitude=None):
    if latitude in (None, "") or longitude in (None, ""):
        return {}
    key = _google_maps_key()
    if not key:
        return {}
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"latlng": f"{latitude},{longitude}", "key": key},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json() or {}
        results = payload.get("results") or []
        if not results:
            return {}
        result = results[0]
        components = result.get("address_components") or []
        parsed = {
            "formatted_address": _clean_map_text(result.get("formatted_address")),
            "address": "",
            "city": "",
            "state": "",
            "state_code": "",
            "zip_code": "",
            "country": "",
        }
        street_number = ""
        route = ""
        for component in components:
            types = set(component.get("types") or [])
            long_name = _clean_map_text(component.get("long_name"))
            short_name = _clean_map_text(component.get("short_name"))
            if "street_number" in types:
                street_number = long_name
            elif "route" in types:
                route = long_name
            elif "locality" in types:
                parsed["city"] = long_name
            elif "administrative_area_level_1" in types:
                parsed["state"] = long_name
                parsed["state_code"] = short_name
            elif "postal_code" in types:
                parsed["zip_code"] = short_name
            elif "country" in types:
                parsed["country"] = long_name
        parsed["address"] = _clean_map_text(" ".join(part for part in [street_number, route] if part))
        return parsed
    except Exception:
        return {}


def _lead_route(name):
    if not name:
        return ""
    return f"{_crm_base_url()}/app/atm-leads/{name}"


def _new_lead_route(query_values=None):
    new_name = f"new-atm-leads-{frappe.generate_hash(length=10).lower()}"
    route = f"{_crm_base_url()}/app/atm-leads/{new_name}"
    if query_values:
        return f"{route}?{urlencode(query_values)}"
    return route


def _zip_row(zip_code=None, state=None):
    filters = {}
    normalized_zip = _normalize_zip(zip_code)
    if normalized_zip:
        filters["zip_code"] = normalized_zip
    state_code = _state_code(state)
    if state_code:
        filters["state_code"] = state_code
    fields = _meta_fields(
        "Zip Code Analytics",
        [
            "name",
            "zip_code",
            "city",
            "state_code",
            "zone_color",
            "zip_score",
            "location_flag",
            "competitor_count",
            "competitor_kiosks",
            "company_kiosks",
        ],
    )
    rows = frappe.get_all("Zip Code Analytics", filters=filters, fields=fields, limit_page_length=3)
    return rows[0] if rows else {}


def _lead_matches(data):
    result = lookup_existing_lead(
        address=data.get("address"),
        zip_code=data.get("zip_code"),
        business_name=data.get("place_name") or data.get("business_name") or data.get("name"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
    )
    return result or {}


def _competitor_match(data):
    return _existing_competitor(
        place_id=data.get("place_id") or data.get("external_id"),
        display_name=data.get("name") or data.get("display_name") or data.get("place_name") or data.get("business_name"),
        address=data.get("address"),
        zip_code=data.get("zip_code"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
    )


def _infer_address_parts(address):
    parts = _address_parts(address)
    return parts.get("city"), parts.get("state_code"), parts.get("zip_code")


def _classify_context(data):
    name = (data.get("name") or data.get("place_name") or data.get("business_name") or "").strip()
    address = (data.get("address") or "").strip()
    category = (data.get("category") or data.get("business_type") or "").strip()
    zip_code = _normalize_zip(data.get("zip_code"))
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not name:
        return "unknown"
    if name.strip().lower() == "google maps":
        return "unknown"
    if category:
        return "business_place"
    if address and zip_code and any(ch.isdigit() for ch in address):
        return "address_place"
    if zip_code and not address and latitude not in (None, "") and longitude not in (None, ""):
        return "zip_area"
    if not address and latitude not in (None, "") and longitude not in (None, ""):
        return "region"
    if not address:
        return "city"
    return "unknown"


def _prefill_values(data):
    raw_zip_code = _normalize_zip(data.get("zip_code"))
    parsed = _address_parts(data.get("address"))
    reverse_parts = {}
    if not (parsed.get("zip_code") and parsed.get("city") and parsed.get("state_code")):
        reverse_parts = _reverse_geocode_parts(data.get("latitude"), data.get("longitude"))
    address = parsed.get("address") or _clean_map_text(data.get("address"))
    address = address or reverse_parts.get("address")
    city = _clean_map_text(data.get("city")) or parsed.get("city")
    city = city or reverse_parts.get("city")
    state_code = _state_code(data.get("state_code") or data.get("state") or parsed.get("state_code") or reverse_parts.get("state_code"))
    state = _state_name(data.get("state") or state_code or parsed.get("state") or reverse_parts.get("state"))
    inferred_city, inferred_state, inferred_zip = _infer_address_parts(address)
    city = city or inferred_city
    state_code = state_code or inferred_state
    state = state or _state_name(state_code)
    zip_code = raw_zip_code or inferred_zip or _normalize_zip(reverse_parts.get("zip_code"))
    if inferred_zip and raw_zip_code and raw_zip_code != inferred_zip:
        # Google Maps parsers sometimes mistake the street number for the ZIP.
        zip_code = inferred_zip
    country = _clean_map_text(data.get("country")) or parsed.get("country") or reverse_parts.get("country") or "United States"
    full_address = _compose_full_address(
        {
            "address": address,
            "city": city,
            "state": state,
            "state_code": state_code,
            "zip_code": zip_code,
            "country": country,
        }
    )
    return {
        "business_name": _clean_map_text(data.get("place_name") or data.get("business_name") or data.get("name")),
        "address": address,
        "full_address": full_address,
        "city": city,
        "state": state,
        "state_code": state_code,
        "zip_code": zip_code,
        "country": country,
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "phone": data.get("phone"),
        "website": data.get("website"),
        "business_type": _map_business_type(data.get("category") or data.get("business_type")),
        "opening_hours_payload": json.dumps(
            _opening_hours_rows(data.get("opening_hours") or data.get("hours")),
            separators=(",", ":"),
        ) if (data.get("opening_hours") or data.get("hours")) else "",
        "source": data.get("source_type") or "Google Maps",
    }


def _zip_summary(zip_row):
    competitor_count = zip_row.get("competitor_count")
    if competitor_count in (None, ""):
        competitor_count = zip_row.get("competitor_kiosks") or 0
    zone_color = zip_row.get("zone_color") or ""
    status = "Proceed"
    if zone_color == "Red":
        status = "Avoid"
    elif zone_color in ("Yellow", "Light Green"):
        status = "Review"
    return {
        "zone_color": zone_color,
        "zip_score": zip_row.get("zip_score") or 0,
        "status": status,
        "competitor_count": competitor_count or 0,
    }


def _safe_json_loads(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {"raw_text": str(value)}


def _lead_scope_rows(zip_code=None, state=None):
    filters = {}
    normalized_zip = _normalize_zip(zip_code)
    if normalized_zip:
        filters["zip_code"] = normalized_zip
    elif state:
        filters["state_code"] = _state_code(state) or state

    requested_fields = [
        "name",
        "business_name",
        "address",
        "city",
        "state",
        "state_code",
        "zip_code",
        "latitude",
        "longitude",
        "workflow_state",
        "business_type",
        "opening_hours",
        "modified",
    ]
    fields = _db_fields("ATM Leads", _meta_fields("ATM Leads", requested_fields))
    rows = frappe.get_all(
        "ATM Leads",
        filters=filters,
        fields=fields,
        limit_page_length=100,
        order_by="modified desc",
    )

    normalized_rows = []
    for row in rows:
        normalized = {field: row.get(field) for field in requested_fields}
        normalized_rows.append(normalized)
    return normalized_rows


def _distance_metrics(prefill=None):
    prefill = prefill or {}
    zip_code = _normalize_zip(prefill.get("zip_code"))
    latitude = prefill.get("latitude")
    longitude = prefill.get("longitude")
    metrics = {
        "distance_threshold_miles": 1.0,
        "nearest_company_miles": None,
        "nearest_competitor_miles": None,
        "meets_company_distance_rule": True,
        "meets_competitor_distance_rule": True,
        "meets_distance_rule": True,
    }
    if not zip_code or latitude in (None, "") or longitude in (None, ""):
        return metrics

    competitor_rows = _competitor_rows_for_zip(zip_code)
    company_rows = _lead_rows_for_zip(zip_code)
    nearest_company = _nearest_distance(latitude, longitude, company_rows)
    nearest_competitor = _nearest_distance(latitude, longitude, competitor_rows)

    metrics["nearest_company_miles"] = round(nearest_company, 2) if nearest_company is not None else None
    metrics["nearest_competitor_miles"] = round(nearest_competitor, 2) if nearest_competitor is not None else None
    metrics["meets_company_distance_rule"] = nearest_company is None or nearest_company > metrics["distance_threshold_miles"]
    metrics["meets_competitor_distance_rule"] = nearest_competitor is None or nearest_competitor > metrics["distance_threshold_miles"]
    metrics["meets_distance_rule"] = metrics["meets_company_distance_rule"] and metrics["meets_competitor_distance_rule"]
    return metrics


def _smart_location_copy(zip_summary, metrics):
    zone_color = (zip_summary.get("zone_color") or "").strip()
    zip_score = float(zip_summary.get("zip_score") or 0)
    favorable_zone = zone_color in ("Green", "Light Green", "Yellow")
    strong_score = zip_score >= 55

    blockers = []
    if zone_color == "Red":
        blockers.append("ZIP is Red under the current criteria rules")
    if not metrics.get("meets_company_distance_rule"):
        blockers.append(
            f"nearest Bitcoin Depot machine is only {metrics.get('nearest_company_miles'):.2f} miles away"
        )
    if not metrics.get("meets_competitor_distance_rule"):
        blockers.append(
            f"nearest competitor kiosk is only {metrics.get('nearest_competitor_miles'):.2f} miles away"
        )

    if favorable_zone and strong_score and metrics.get("meets_distance_rule"):
        return (
            "This location will have more chance to win. "
            "ZIP score is good, the zone is favorable, and the kiosk distance metrics meet the 1 mile rule."
        )

    if blockers:
        return "Manual review is important here because " + "; ".join(blockers) + "."

    if favorable_zone:
        return (
            "This location may still have a chance to win, but the kiosk distance metrics are important "
            "and should be reviewed before moving forward."
        )

    return "This location does not look strong under the current ZIP criteria and distance rules."


def _control_panel_context(data, prefill=None):
    prefill = prefill or _prefill_values(data)
    zip_row = _zip_row(zip_code=prefill.get("zip_code"), state=prefill.get("state_code") or prefill.get("state"))
    zip_summary = _zip_summary(zip_row)
    distance_metrics = _distance_metrics(prefill)
    scope_leads = _lead_scope_rows(zip_code=prefill.get("zip_code"), state=prefill.get("state_code") or prefill.get("state"))
    demo_summary = _safe_json_loads(zip_row.get("demo_json"))
    ai_hint = {}
    if prefill.get("zip_code"):
        ai_hint = generate_zip_ai_hint(
            prefill.get("zip_code"),
            place_context={
                "business_name": prefill.get("business_name"),
                "category": data.get("category") or prefill.get("business_type"),
                "address": prefill.get("address"),
                "city": prefill.get("city"),
                "state_code": prefill.get("state_code"),
                "google_rating": data.get("google_rating"),
                "user_ratings_total": data.get("user_ratings_total"),
                "open_now_text": data.get("open_now_text"),
                "website": prefill.get("website"),
                "phone": prefill.get("phone"),
                "distance_metrics": distance_metrics,
                "zip_score": zip_summary.get("zip_score"),
                "zone_color": zip_summary.get("zone_color"),
            },
        ) or {}
    if not ai_hint and demo_summary.get("raw_text"):
        ai_hint = {
            "provider": demo_summary.get("provider") or "stored",
            "raw_text": demo_summary.get("raw_text"),
        }

    leads = []
    for row in scope_leads[:12]:
        leads.append(
            {
                "atm_lead_name": row.get("name"),
                "business_name": row.get("business_name"),
                "address": row.get("address"),
                "city": row.get("city"),
                "state": row.get("state_code") or row.get("state"),
                "zip_code": row.get("zip_code"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "workflow_state": row.get("workflow_state"),
                "business_type": row.get("business_type"),
                "opening_hours": row.get("opening_hours"),
                "modified": row.get("modified"),
            }
        )

    return {
        "zip": {
            "zip_code": zip_row.get("zip_code") or prefill.get("zip_code") or "",
            "city": zip_row.get("city") or prefill.get("city") or "",
            "state_code": zip_row.get("state_code") or prefill.get("state_code") or "",
            "zone_color": zip_summary.get("zone_color") or "",
            "zip_score": zip_summary.get("zip_score") or 0,
            "status": zip_summary.get("status") or "Review",
            "population": zip_row.get("population") or 0,
            "population_density": zip_row.get("population_density") or 0,
            "competitor_density": zip_row.get("competitor_density") or 0,
            "competitor_kiosks": zip_row.get("competitor_kiosks") or 0,
            "company_kiosks": zip_row.get("company_kiosks") or 0,
            "total_kiosks": zip_row.get("total_kiosks") or 0,
            "matched_rule": zip_row.get("matched_rule") or "",
            "location_flag": zip_row.get("location_flag") or "",
            "summary": demo_summary,
        },
        "metrics": distance_metrics,
        "decision_copy": _smart_location_copy(zip_summary, distance_metrics),
        "lead_scope": {
            "count": len(scope_leads),
            "leads": leads,
        },
        "ai": {
            "provider": ai_hint.get("provider") or "",
            "raw_text": ai_hint.get("raw_text") or "",
            "available": bool(ai_hint.get("available") if "available" in ai_hint else ai_hint),
            "reason": ai_hint.get("reason") or "",
            "summary": ai_hint.get("summary") or "",
            "next_action": ai_hint.get("next_action") or "",
            "caution": ai_hint.get("caution") or "",
            "foot_traffic_estimate": ai_hint.get("foot_traffic_estimate") or "",
            "suitability_note": ai_hint.get("suitability_note") or "",
        },
    }


def _validation_message(zip_row, lead_match, competitor_match, context_type=None):
    best = lead_match.get("best_match") or {}
    duplicate_found = bool(best)
    zip_summary = _zip_summary(zip_row)
    recommendation = "Create Prefilled ATM Lead"
    duplicate_reason = ""
    if duplicate_found:
        recommendation = "Open Existing Lead"
        duplicate_reason = f"Location already exists in ATM Leads at workflow state {best.get('workflow_state') or 'Unknown'}"
    elif zip_summary["status"] == "Avoid":
        recommendation = "Avoid"
        duplicate_reason = "ZIP is marked Red in Zip Code Analytics"
    elif zip_summary["status"] == "Review":
        recommendation = "Manual Review"
    if not zip_summary["zone_color"] and not duplicate_found:
        zip_summary["status"] = "Review"
        recommendation = "Manual Review"
    if context_type and context_type not in ("business_place", "address_place") and not duplicate_found:
        recommendation = "Manual Review"

    return {
        "exists_in_atm_leads": duplicate_found,
        "existing_lead_name": best.get("name") or "",
        "workflow_state": best.get("workflow_state") or "",
        "exists_in_competitors": bool(competitor_match),
        "zip_score": zip_summary["zip_score"],
        "zone_color": zip_summary["zone_color"],
        "recommendation": recommendation,
        "duplicate_reason": duplicate_reason,
        "competitor_count": zip_summary["competitor_count"],
        "open_existing_lead_url": _lead_route(best.get("name")),
        "allowed": not duplicate_found and zip_summary["status"] != "Avoid",
        "status": zip_summary["status"],
    }


@frappe.whitelist()
def prefill_atm_lead_context(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    prefill = _prefill_values(data)
    context_type = _classify_context(data)
    zip_row = _zip_row(zip_code=prefill.get("zip_code"), state=prefill.get("state"))
    lead_match = _lead_matches(data)
    competitor_match = _competitor_match(data)
    validation = _validation_message(zip_row, lead_match, competitor_match, context_type=context_type)

    warnings = []
    can_create_lead = context_type in ("business_place", "address_place")
    if context_type not in ("business_place", "address_place"):
        warnings.append("This is an area-level or weak map result, not a specific business location.")
    if validation["exists_in_atm_leads"]:
        warnings.append(f"This location already exists at workflow state: {validation['workflow_state'] or 'Unknown'}")

    query_values = {
        key: value
        for key, value in prefill.items()
        if value not in (None, "") and key not in ("opening_hours", "hours")
    }
    open_url = _new_lead_route(query_values)

    message = {
        "context_type": context_type,
        "can_create_lead": can_create_lead and not validation["exists_in_atm_leads"],
        "requires_manual_review": context_type not in ("business_place", "address_place") or validation["status"] == "Review",
        "duplicate_found": validation["exists_in_atm_leads"],
        "workflow_state": validation["workflow_state"],
        "existing_lead_name": validation["existing_lead_name"],
        "existing_route": validation["open_existing_lead_url"],
        "open_existing_lead_url": validation["open_existing_lead_url"],
        "prefill": prefill,
        "route": open_url,
        "open_url": open_url,
        "crm_base_url": _crm_base_url(),
        "warnings": warnings,
        "hints": {
            "zone_color": validation["zone_color"],
            "zip_score": validation["zip_score"],
            "status": validation["status"],
            "competitor_count": validation["competitor_count"],
        },
        "control_panel": _control_panel_context(data, prefill=prefill),
    }
    if validation["exists_in_atm_leads"]:
        message["warning"] = warnings[-1]
    elif not can_create_lead:
        message["warning"] = warnings[0]

    return {
        "message": message,
        "open_url": open_url,
        "crm_base_url": _crm_base_url(),
        "warning": message.get("warning"),
        "route": open_url,
        "prefill": prefill,
        "duplicate_found": validation["exists_in_atm_leads"],
        "existing_lead_name": validation["existing_lead_name"],
        "workflow_state": validation["workflow_state"],
        "existing_route": validation["open_existing_lead_url"],
    }


@frappe.whitelist()
def get_map_decision_panel(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    prefill = _prefill_values(data)
    context_type = _classify_context(data)
    zip_row = _zip_row(zip_code=prefill.get("zip_code"), state=prefill.get("state"))
    lead_match = _lead_matches(data)
    competitor_match = _competitor_match(data)
    validation = _validation_message(zip_row, lead_match, competitor_match, context_type=context_type)
    return {
        "message": {
            "context_type": context_type,
            "prefill": prefill,
            "validation": validation,
            "control_panel": _control_panel_context(data, prefill=prefill),
            "crm_base_url": _crm_base_url(),
        }
    }


@frappe.whitelist()
def sync_zip_cache_scope(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    zip_code = _normalize_zip(data.get("zip_code"))
    state = data.get("state") or data.get("state_code")
    row = _zip_row(zip_code=zip_code, state=state)
    if not row:
        return {"message": {"zips": []}, "zips": []}

    zips = [
        {
            "zip_code": row.get("zip_code"),
            "city": row.get("city"),
            "state": row.get("state_code"),
            "zone_color": row.get("zone_color"),
            "zip_score": row.get("zip_score"),
            "competitor_count": _zip_summary(row)["competitor_count"],
            "our_lead_count": row.get("company_kiosks") or 0,
            "validation_status": row.get("location_flag") or "",
        }
    ]
    return {"message": {"zips": zips}, "zips": zips}


@frappe.whitelist()
def sync_lead_cache_scope(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    zip_code = _normalize_zip(data.get("zip_code"))
    filters = {"zip_code": zip_code} if zip_code else {}
    state = data.get("state") or data.get("state_code")
    if state and not zip_code:
        filters["state"] = state

    rows = frappe.get_all(
        "ATM Leads",
        filters=filters,
        fields=["name", "business_name", "address", "zip_code", "state", "state_code", "latitude", "longitude", "workflow_state", "modified"],
        limit_page_length=100,
        order_by="modified desc",
    )
    leads = []
    for row in rows:
        leads.append(
            {
                "atm_lead_name": row.get("name"),
                "business_name": row.get("business_name"),
                "address": row.get("address"),
                "zip_code": row.get("zip_code"),
                "state": row.get("state_code") or row.get("state"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "workflow_state": row.get("workflow_state"),
                "modified": row.get("modified"),
            }
        )
    return {"message": {"leads": leads}, "leads": leads}


@frappe.whitelist()
def sync_competitor_cache_scope(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    zip_code = _normalize_zip(data.get("zip_code"))
    filters = {"actual_zip_code": zip_code} if zip_code else {}
    state = data.get("state") or data.get("state_code")
    if state and not zip_code:
        filters["state_code"] = state

    rows = frappe.get_all(
        "Competitor Kiosk",
        filters=filters,
        fields=["name", "place_id", "display_name", "address", "actual_zip_code", "state_code", "latitude", "longitude", "source", "provider"],
        limit_page_length=100,
        order_by="modified desc",
    )
    competitors = []
    for row in rows:
        competitors.append(
            {
                "external_id": row.get("place_id"),
                "name": row.get("display_name"),
                "address": row.get("address"),
                "zip_code": row.get("actual_zip_code"),
                "state": row.get("state_code"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "source_url": row.get("source"),
                "source_type": row.get("provider"),
                "synced_to_crm": True,
                "crm_competitor_kiosk_name": row.get("name"),
            }
        )
    return {"message": {"competitors": competitors}, "competitors": competitors}


@frappe.whitelist()
def validate_location_scope(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    context_type = _classify_context(data)
    prefill = _prefill_values(data)
    zip_row = _zip_row(zip_code=prefill.get("zip_code"), state=prefill.get("state"))
    lead_match = _lead_matches(data)
    competitor_match = _competitor_match(data)
    message = _validation_message(zip_row, lead_match, competitor_match, context_type=context_type)
    message["context_type"] = context_type
    message["prefill"] = prefill
    message["control_panel"] = _control_panel_context(data, prefill=prefill)
    return {
        "message": message,
        "allowed": message["allowed"],
        "status": message["status"],
        "zone_color": message["zone_color"],
        "zip_score": message["zip_score"],
        "duplicate_found": message["exists_in_atm_leads"],
        "workflow_state": message["workflow_state"],
        "existing_lead_name": message["existing_lead_name"],
        "reason": message["duplicate_reason"],
        "recommended_action": message["recommendation"],
        "competitor_count": message["competitor_count"],
    }


@frappe.whitelist()
def upsert_competitor_kiosk(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    created = upsert_competitor_kiosk_from_radar(
        place_id=_clip(data.get("place_id") or data.get("external_id")),
        display_name=_clip(data.get("name") or data.get("display_name")),
        address=_clip(data.get("address")),
        city=_clip(data.get("city")),
        state_code=_clip(data.get("state") or data.get("state_code")),
        zip_code=data.get("zip_code"),
        actual_zip_code=data.get("zip_code"),
        country=data.get("country") or "United States",
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        source=_clip(data.get("source_url")),
        provider=_clip(data.get("source_type") or "google_maps"),
        brand=_clip(data.get("brand") or "Unknown"),
    )
    message = {
        "status": "created" if created.get("created", False) else "upserted",
        "competitor_kiosk_name": created.get("name"),
        "dedup_reason": "" if created.get("created", False) else "Existing competitor kiosk matched by place, address, name+zip, or nearby coordinates",
    }
    return {
        "message": message,
        "name": created.get("name"),
        "created": created.get("created", False),
        "duplicate": not created.get("created", False),
    }


@frappe.whitelist()
def get_browser_notifications(payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    employee = data.get("employee")
    user = frappe.db.get_value("Employee", employee, "user_id") if employee else frappe.session.user
    if not user or user == "Guest":
        return {"message": []}

    rows = frappe.get_all(
        "Notification Log",
        filters={"for_user": user, "read": 0},
        fields=["name", "subject", "email_content", "document_type", "document_name", "creation"],
        order_by="creation desc",
        limit_page_length=10,
    )
    notifications = []
    for row in rows:
        notifications.append(
            {
                "notification_id": row.get("name"),
                "title": row.get("subject") or "CRM Notification",
                "message": frappe.safe_decode(row.get("email_content") or row.get("subject") or "").strip()[:280],
                "created_at": row.get("creation"),
                "document_type": row.get("document_type"),
                "document_name": row.get("document_name"),
            }
        )
    return {"message": notifications}


@frappe.whitelist()
def ack_browser_notification(notification_id=None, payload=None, **kwargs):
    data = _request_context(payload, **kwargs)
    target_notification = notification_id or data.get("notification_id")
    if not target_notification:
        return {"message": {"ok": False, "reason": "missing_notification_id"}}

    if frappe.db.exists("Notification Log", target_notification):
        frappe.db.set_value("Notification Log", target_notification, {"read": 1, "seen": 1}, update_modified=False)
    return {
        "message": {
            "ok": True,
            "notification_id": target_notification,
            "acked_at": str(now_datetime()),
        }
    }
