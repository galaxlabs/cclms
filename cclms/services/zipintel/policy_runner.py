import json
from collections import Counter

import frappe
from frappe.utils import flt, now_datetime


ZONE_COLOR_MAP = {
    "Green": "Green",
    "Light Green": "Light Green",
    "Yellow": "Yellow",
    "Red": "Red",
}


def _z5(value):
    return str(value or "").zfill(5)


def _load_rules():
    cfg = frappe.get_single("ATM Criteria")
    rules = [row for row in (cfg.rules or []) if int(row.active or 0) == 1]
    rules.sort(key=lambda row: int(row.priority or 0), reverse=True)
    return cfg, rules


def _brand_summary(zip_code):
    rows = frappe.get_all(
        "Competitor Kiosk",
        filters={"actual_zip_code": zip_code},
        fields=["brand"],
        limit_page_length=1000,
    )
    if not rows:
        rows = frappe.get_all(
            "Competitor Kiosk",
            filters={"zip_code": zip_code},
            fields=["brand"],
            limit_page_length=1000,
        )

    counts = Counter((row.brand or "Unknown").strip() for row in rows if row.get("brand"))
    return counts.most_common(5)


def _company_kiosks_for_zip(zip_code):
    return frappe.db.count("ATM Leads", filters={"zip_code": zip_code})


def _competitor_kiosks_for_zip(zip_code):
    actual = frappe.db.sql(
        """
        SELECT COUNT(*) AS cnt
        FROM `tabCompetitor Kiosk`
        WHERE actual_zip_code = %s
        """,
        (zip_code,),
        as_dict=True,
    )[0].cnt
    if actual:
        return int(actual)

    fallback = frappe.db.sql(
        """
        SELECT COUNT(*) AS cnt
        FROM `tabCompetitor Kiosk`
        WHERE zip_code = %s
        """,
        (zip_code,),
        as_dict=True,
    )[0].cnt
    return int(fallback or 0)


def _score_zip(row):
    pop = flt(row.get("population"))
    dens = flt(row.get("population_density"))
    margin = flt(row.get("margin"))
    removal = flt(row.get("removal_rate"))
    competitor = flt(row.get("competitor_kiosks"))
    company = flt(row.get("company_kiosks"))
    total = flt(row.get("total_kiosks"))
    location_flag = (row.get("location_flag") or "").strip()

    score = 0.0
    score += min(30.0, pop / 4000.0)
    score += min(25.0, dens / 80.0)
    score += min(20.0, max(0.0, margin) * 0.8)
    score += max(0.0, 20.0 - competitor * 4.0)
    score += max(0.0, 15.0 - company * 5.0)
    score += max(0.0, 10.0 - total * 1.5)
    score -= min(25.0, removal * 100.0 * 0.5)
    if location_flag == "Meets Pop Threshold":
        score += 10.0
    elif location_flag == "Below Pop Threshold":
        score -= 20.0
    return round(max(0.0, min(100.0, score)), 2)


def _rule_matches(rule, row):
    pop = flt(row.get("population"))
    dens = flt(row.get("population_density"))
    competitor = flt(row.get("competitor_kiosks"))
    company = flt(row.get("company_kiosks"))
    total = flt(row.get("total_kiosks"))
    score = flt(row.get("zip_score"))
    removal = flt(row.get("removal_rate")) / 100.0 if flt(row.get("removal_rate")) > 1 else flt(row.get("removal_rate"))

    if flt(rule.population_min) and pop < flt(rule.population_min):
        return False
    if flt(rule.population_max) and pop > flt(rule.population_max):
        return False
    if flt(rule.density_min) and dens < flt(rule.density_min):
        return False
    if flt(rule.density_max) and dens > flt(rule.density_max):
        return False
    if flt(rule.competitor_min) and competitor < flt(rule.competitor_min):
        return False
    if flt(rule.competitor_max) and competitor > flt(rule.competitor_max):
        return False
    if flt(rule.total_kiosks_min) and total < flt(rule.total_kiosks_min):
        return False
    if flt(rule.total_kiosks_max) and total > flt(rule.total_kiosks_max):
        return False
    if flt(rule.company_kiosks_max) and company > flt(rule.company_kiosks_max):
        return False
    if flt(rule.zip_score_min) and score < flt(rule.zip_score_min):
        return False
    if flt(rule.zip_score_max) and score > flt(rule.zip_score_max):
        return False
    if flt(rule.removal_ratio_max) and removal > flt(rule.removal_ratio_max):
        return False
    return True


def _classify_row(row, rules):
    for rule in rules:
        if _rule_matches(rule, row):
            zone = rule.zone_label or rule.rule_name or "Red"
            return zone, rule.rule_name
    return "Red", None


def refresh_zip_record(zip_code):
    zip_code = _z5(zip_code)
    row = frappe.db.get_value("Zip Code Analytics", {"zip_code": zip_code}, "*", as_dict=True)
    if not row:
        return {"status": "missing", "zip_code": zip_code}

    company = _company_kiosks_for_zip(zip_code)
    competitor = _competitor_kiosks_for_zip(zip_code)
    total = company + competitor

    values = dict(row)
    values["company_kiosks"] = company
    values["competitor_kiosks"] = competitor
    values["competitor_density"] = competitor
    values["total_kiosks"] = total
    values["zip_score"] = _score_zip(values)

    _, rules = _load_rules()
    zone, matched_rule = _classify_row(values, rules)
    summary = {
        "zip_code": zip_code,
        "zone_color": zone,
        "zip_score": values["zip_score"],
        "company_kiosks": company,
        "competitor_kiosks": competitor,
        "top_competitors": _brand_summary(zip_code),
        "suggestion": (
            "Prioritize outreach" if zone in ("Green", "Light Green")
            else "Review manually" if zone == "Yellow"
            else "Hold unless a stronger business case appears"
        ),
        "generated_on": str(now_datetime()),
    }

    frappe.db.set_value(
        "Zip Code Analytics",
        row.name,
        {
            "company_kiosks": company,
            "competitor_kiosks": competitor,
            "competitor_density": competitor,
            "total_kiosks": total,
            "zip_score": values["zip_score"],
            "zone_color": ZONE_COLOR_MAP.get(zone, zone),
            "matched_rule": matched_rule,
            "last_score_update": now_datetime(),
            "zone_updated_on": now_datetime(),
            "demo_json": json.dumps(summary, indent=2),
        },
        update_modified=False,
    )
    return {"status": "ok", **summary}


def seed_all_zip_scores(limit=0, offset=0, commit_every=200):
    rows = frappe.get_all(
        "Zip Code Analytics",
        fields=["name", "zip_code"],
        order_by="zip_code asc",
        start=int(offset),
        limit_page_length=int(limit) if int(limit or 0) else 0,
    )

    updated = 0
    for idx, row in enumerate(rows, start=1):
        result = refresh_zip_record(row.zip_code)
        if result.get("status") == "ok":
            updated += 1
        if commit_every and idx % int(commit_every) == 0:
            frappe.db.commit()

    frappe.db.commit()
    return {"processed": len(rows), "updated": updated, "next_offset": int(offset) + len(rows)}


def run_daily_zip_policy(limit=1):
    policy = frappe.get_single("AI Policy")
    if not int(policy.enable_ai_enrichment or 0):
        return {"ok": False, "msg": "AI Policy disabled"}

    cfg = frappe.get_single("ATM Criteria")
    cursor = _z5(cfg.last_zip_cursor or "00000")
    rows = frappe.get_all(
        "Zip Code Analytics",
        fields=["zip_code"],
        filters={"zip_code": [">", cursor]},
        order_by="zip_code asc",
        limit_page_length=max(1, int(limit or 1)),
    )
    if not rows:
        rows = frappe.get_all(
            "Zip Code Analytics",
            fields=["zip_code"],
            order_by="zip_code asc",
            limit_page_length=max(1, int(limit or 1)),
        )

    processed = []
    for row in rows:
        processed.append(refresh_zip_record(row.zip_code))
        cfg.last_zip_cursor = _z5(row.zip_code)

    cfg.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "processed": processed, "last_zip_cursor": cfg.last_zip_cursor}
