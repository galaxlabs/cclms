import frappe
from frappe import _

from cclms.services.mirror.operator_deal_sync import build_address_fingerprint, normalize_text


def _candidate_rows(zip_code):
    filters = {}
    if zip_code:
        filters["zip_code"] = str(zip_code).strip()
    return frappe.get_all(
        "ATM Leads",
        filters=filters,
        fields=[
            "name",
            "business_name",
            "company",
            "workflow_state",
            "address",
            "full_address",
            "zip_code",
            "city",
            "state",
            "state_code",
            "latitude",
            "longitude",
            "executive_name",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=200,
    )


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


def _score_match(row, fingerprint, business_name=None, latitude=None, longitude=None):
    score = 0
    row_fp = build_address_fingerprint(row.get("address") or row.get("full_address"), row.get("zip_code"))
    if fingerprint and row_fp == fingerprint:
        score += 100

    if business_name and normalize_text(row.get("business_name")) == normalize_text(business_name):
        score += 25

    if latitude not in (None, "") and longitude not in (None, "") and row.get("latitude") and row.get("longitude"):
        distance = _mile_distance(latitude, longitude, row.get("latitude"), row.get("longitude"))
        if distance is not None:
            row["distance_miles"] = round(distance, 2)
            if distance <= 0.1:
                score += 35
            elif distance <= 0.5:
                score += 15
    return score


@frappe.whitelist()
def lookup_existing_lead(address=None, zip_code=None, business_name=None, latitude=None, longitude=None):
    fingerprint = build_address_fingerprint(address, zip_code)
    rows = _candidate_rows(zip_code)

    matches = []
    for row in rows:
        score = _score_match(row, fingerprint, business_name=business_name, latitude=latitude, longitude=longitude)
        if score <= 0:
            continue
        row["match_score"] = score
        row["route"] = ["Form", "ATM Leads", row["name"]]
        matches.append(row)

    matches.sort(key=lambda row: (row.get("match_score") or 0, row.get("modified") or ""), reverse=True)
    best = matches[0] if matches else None
    return {
        "exists": bool(best),
        "best_match": best,
        "matches": matches[:10],
        "message": (
            _("Lead already exists in stage {0}").format(best.get("workflow_state"))
            if best
            else _("No existing ATM Lead found for this location")
        ),
    }

