import frappe
from frappe.utils import flt, now_datetime
from cclms.services.zipintel.policy_runner import _score_zip
from cclms.services.zipintel.intelligence import build_lead_intelligence


def _normalize_score(value, floor=0, ceiling=100):
    return max(floor, min(ceiling, flt(value)))


def _compute_scores(zip_row):
    zip_score = flt(zip_row.get("zip_score") or _score_zip(zip_row))
    competitor_density = flt(zip_row.get("competitor_density") or zip_row.get("competitor_kiosks"))
    removal_rate = flt(zip_row.get("removal_rate"))
    saturation_rate = flt(zip_row.get("saturation_rate"))
    population_density = flt(zip_row.get("population_density"))

    competitor_density_score = _normalize_score(100 - (competitor_density * 10))
    risk_score = _normalize_score((removal_rate * 100) + saturation_rate + (25 if zip_row.get("zone_color") == "Red" else 0))
    operator_fit_score = _normalize_score((zip_score * 0.6) + (population_density / 100) + competitor_density_score * 0.2 - risk_score * 0.2)

    return competitor_density_score, risk_score, operator_fit_score


def enrich_operator_deals(limit=200, offset=0, commit_every=100):
    deals = frappe.db.sql(
        """
        SELECT
            od.name,
            od.operator_company,
            od.location,
            od.source_atm_lead,
            loc.zip_code
        FROM `tabOperator Deal` od
        LEFT JOIN `tabBTM Location` loc ON loc.name = od.location
        ORDER BY od.modified ASC
        LIMIT %(offset)s, %(limit)s
        """,
        {"offset": int(offset), "limit": int(limit)},
        as_dict=True,
    )

    updated = 0
    skipped = 0
    missing_zip = 0

    for idx, deal in enumerate(deals, start=1):
        zip_code = (deal.zip_code or "").strip()
        if not zip_code:
            skipped += 1
            missing_zip += 1
            continue

        zip_row = frappe.db.get_value("Zip Code Analytics", {"zip_code": zip_code}, "*", as_dict=True)
        if not zip_row:
            skipped += 1
            missing_zip += 1
            continue

        competitor_density_score, risk_score, operator_fit_score = _compute_scores(zip_row)
        intelligence = {}
        if deal.get("source_atm_lead") and frappe.db.exists("ATM Leads", deal.get("source_atm_lead")):
            intelligence = build_lead_intelligence(deal.get("source_atm_lead"), write_zip_centroid=True)

        zone = intelligence.get("zone_color") or zip_row.get("zone_color") or zip_row.get("zone")
        next_action = intelligence.get("recommended_next_action")
        if not next_action:
            if zone == "Green":
                next_action = "Prioritize owner outreach and operator submission."
            elif zone == "Light Green":
                next_action = "Advance after quick qualification review."
            elif zone == "Yellow":
                next_action = "Manual review with ZIP context before submission."
            else:
                next_action = "Hold by default; require manager review or stronger data."

        values = {
            "tier_suggestion": zone,
            "competitor_density_score": intelligence.get("competitor_density_score", competitor_density_score),
            "risk_score": intelligence.get("risk_score", risk_score),
            "operator_fit_score": intelligence.get("operator_fit_score", operator_fit_score),
            "recommended_next_action": next_action,
            "zip_matched_rule": intelligence.get("matched_rule") or zip_row.get("matched_rule"),
            "last_enriched_on": now_datetime(),
        }
        frappe.db.set_value("Operator Deal", deal.name, values, update_modified=False)
        updated += 1

        if commit_every and idx % int(commit_every) == 0:
            frappe.db.commit()

    frappe.db.commit()
    return {
        "processed": len(deals),
        "updated": updated,
        "skipped": skipped,
        "missing_zip": missing_zip,
        "next_offset": int(offset) + len(deals),
    }
