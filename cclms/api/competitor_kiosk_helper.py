import frappe
from frappe import _
from frappe.utils import now_datetime


USA_NAMES = {"united states", "united states of america", "usa", "us"}


def _normalize_text(value):
    return " ".join(str(value or "").strip().lower().split())


def _normalize_zip(value):
    value = str(value or "").strip()
    return value.zfill(5) if value.isdigit() else value


def _clip(value, length=140):
    if value in (None, ""):
        return value
    return str(value)[:length]


def _is_usa(country):
    return _normalize_text(country) in USA_NAMES


def _mile_distance(lat1, lng1, lat2, lng2):
    try:
        from math import atan2, cos, radians, sin, sqrt

        lat1 = float(lat1)
        lng1 = float(lng1)
        lat2 = float(lat2)
        lng2 = float(lng2)
    except Exception:
        return None

    radius_miles = 3958.7613
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * radius_miles * atan2(sqrt(a), sqrt(1 - a))


def _existing_competitor(place_id=None, display_name=None, address=None, zip_code=None, latitude=None, longitude=None):
    if place_id:
        row = frappe.db.get_value(
            "Competitor Kiosk",
            {"place_id": place_id},
            ["name", "brand", "display_name", "address", "city", "state_code", "zip_code", "actual_zip_code", "latitude", "longitude", "source", "provider", "last_seen_on"],
            as_dict=True,
        )
        if row:
            row["duplicate_reason"] = "place_id"
            return row

    zip_code = _normalize_zip(zip_code)
    candidates = frappe.get_all(
        "Competitor Kiosk",
        filters={"actual_zip_code": zip_code} if zip_code else {},
        fields=["name", "brand", "display_name", "address", "city", "state_code", "zip_code", "actual_zip_code", "latitude", "longitude", "source", "provider", "last_seen_on", "place_id"],
        limit_page_length=200,
        order_by="modified desc",
    )

    target_name = _normalize_text(display_name)
    target_address = _normalize_text(address)
    for row in candidates:
        if target_address and _normalize_text(row.get("address")) == target_address:
            row["duplicate_reason"] = "address"
            return row
        if target_name and _normalize_text(row.get("display_name")) == target_name and _normalize_zip(row.get("actual_zip_code") or row.get("zip_code")) == zip_code:
            row["duplicate_reason"] = "display_name_zip"
            return row
        distance = _mile_distance(latitude, longitude, row.get("latitude"), row.get("longitude"))
        if distance is not None and distance <= 0.05:
            row["duplicate_reason"] = "nearby_coordinates"
            row["distance_miles"] = round(distance, 3)
            return row

    return None


@frappe.whitelist()
def lookup_competitor_kiosk(place_id=None, display_name=None, address=None, zip_code=None, actual_zip_code=None, latitude=None, longitude=None, country=None):
    country = country or ""
    if country and not _is_usa(country):
        return {
            "allowed": False,
            "exists": False,
            "message": _("Only USA locations can be saved as Competitor Kiosk"),
        }

    row = _existing_competitor(
        place_id=place_id,
        display_name=display_name,
        address=address,
        zip_code=actual_zip_code or zip_code,
        latitude=latitude,
        longitude=longitude,
    )
    return {
        "allowed": True,
        "exists": bool(row),
        "existing": row,
        "message": _("Competitor kiosk already exists") if row else _("No competitor kiosk duplicate found"),
    }


@frappe.whitelist()
def upsert_competitor_kiosk_from_radar(
    place_id=None,
    display_name=None,
    address=None,
    city=None,
    state_code=None,
    zip_code=None,
    actual_zip_code=None,
    country=None,
    latitude=None,
    longitude=None,
    source=None,
    provider=None,
    brand=None,
):
    if not _is_usa(country):
        frappe.throw(_("Only USA locations can be saved as Competitor Kiosk"))

    existing = _existing_competitor(
        place_id=place_id,
        display_name=display_name,
        address=address,
        zip_code=actual_zip_code or zip_code,
        latitude=latitude,
        longitude=longitude,
    )

    values = {
        "brand": _clip(brand or "Unknown"),
        "display_name": _clip(display_name),
        "address": _clip(address),
        "city": _clip(city),
        "state_code": _clip(state_code),
        "zip_code": _normalize_zip(zip_code),
        "actual_zip_code": _normalize_zip(actual_zip_code or zip_code),
        "latitude": latitude,
        "longitude": longitude,
        "source": _clip(source or "btm-radar"),
        "provider": _clip(provider or "Google Maps"),
        "last_seen_on": now_datetime(),
        "active": 1,
    }

    if existing:
        frappe.db.set_value("Competitor Kiosk", existing.name, values, update_modified=True)
        return {
            "created": False,
            "updated": True,
            "name": existing.name,
            "duplicate_reason": existing.get("duplicate_reason"),
        }

    doc = frappe.get_doc(
        {
            "doctype": "Competitor Kiosk",
            "place_id": _clip(place_id or frappe.generate_hash(length=12)),
            "first_seen_on": now_datetime(),
            **values,
        }
    )
    doc.insert(ignore_permissions=True)
    return {"created": True, "updated": False, "name": doc.name}
