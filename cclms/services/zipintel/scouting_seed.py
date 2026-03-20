import csv
import json

import frappe
from frappe.utils import flt

from cclms.services.zipintel.policy_runner import refresh_zip_record


CSV_PATH = "/home/dg/dg-b/sites/crm.galaxylabs.online/private/files/Zip Codes Scouting Report - 10.06.csv"


def _num(value):
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _z5(value):
    return str(value or "").zfill(5)


def _read_csv(path=CSV_PATH):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            zip_code = _z5(row.get("zip_code") or row.get("Zip5"))
            if not zip_code or zip_code == "00000":
                continue
            yield row, zip_code


def seed_zip_analytics_from_csv(path=CSV_PATH, limit=0):
    processed = 0
    inserted = 0
    updated = 0

    for row, zip_code in _read_csv(path):
        processed += 1
        if limit and processed > int(limit):
            break

        existing = frappe.db.get_value("Zip Code Analytics", {"zip_code": zip_code}, "name")
        doc = frappe.get_doc("Zip Code Analytics", existing) if existing else frappe.new_doc("Zip Code Analytics")

        doc.zip_code = zip_code
        doc.city = row.get("City")
        doc.state_code = row.get("State")
        doc.location_flag = row.get("Location Analytics Flag")
        doc.population = int(_num(row.get("Blended Pop Estimate")) or 0)
        doc.population_density = flt(_num(row.get("Pop Density")) or 0)
        doc.square_miles = flt(_num(row.get("Square Miles")) or 0)
        doc.total_kiosks = int(_num(row.get("total_kiosks")) or 0)
        doc.company_kiosks = int(_num(row.get("bcd_kiosks")) or 0)
        doc.margin = flt(_num(row.get("Margin")) or 0)
        doc.kiosks_installed = int(_num(row.get("kiosks_installed")) or 0)
        doc.kiosks_pending_removal = int(_num(row.get("kiosks_pending_removal")) or 0)
        doc.kiosks_removed = int(_num(row.get("kiosks_removed")) or 0)
        doc.removal_rate = flt(_num(row.get("Removal Rate")) or 0)
        doc.geo_id_fq = row.get("geo_id_fq")
        doc.land_sq_mi = flt(_num(row.get("Land_SQMI_from_gaz")) or 0)
        doc.water_sq_mi = flt(_num(row.get("Water_SQMI_from_gaz")) or 0)
        doc.latitude = flt(_num(row.get("Latitude_from_gaz")) or 0)
        doc.longitude = flt(_num(row.get("Longitude_from_gaz")) or 0)
        doc.demo_json = json.dumps({"seed_source": "Zip Codes Scouting Report - 10.06.csv"}, indent=2)

        if existing:
            doc.save(ignore_permissions=True)
            updated += 1
        else:
            doc.insert(ignore_permissions=True)
            inserted += 1

    frappe.db.commit()
    return {"processed": processed if not limit else min(processed, int(limit)), "inserted": inserted, "updated": updated}


def seed_rules_from_csv():
    cfg = frappe.get_single("ATM Criteria")
    rules = [
        {
            "rule_name": "CSV Green Approval",
            "zone_label": "Green",
            "priority": 400,
            "population_min": 40000,
            "population_max": 0,
            "density_min": 500,
            "density_max": 0,
            "competitor_min": 0,
            "competitor_max": 2,
            "total_kiosks_min": 0,
            "total_kiosks_max": 4,
            "company_kiosks_max": 1,
            "removal_ratio_max": 0.60,
            "zip_score_min": 75,
            "zip_score_max": 0,
            "color_code": "#16a34a",
            "active": 1,
        },
        {
            "rule_name": "CSV Light Green Approval",
            "zone_label": "Light Green",
            "priority": 300,
            "population_min": 25000,
            "population_max": 0,
            "density_min": 250,
            "density_max": 0,
            "competitor_min": 0,
            "competitor_max": 4,
            "total_kiosks_min": 0,
            "total_kiosks_max": 6,
            "company_kiosks_max": 2,
            "removal_ratio_max": 0.75,
            "zip_score_min": 55,
            "zip_score_max": 0,
            "color_code": "#84cc16",
            "active": 1,
        },
        {
            "rule_name": "CSV Yellow Review",
            "zone_label": "Yellow",
            "priority": 200,
            "population_min": 10000,
            "population_max": 0,
            "density_min": 75,
            "density_max": 0,
            "competitor_min": 0,
            "competitor_max": 8,
            "total_kiosks_min": 0,
            "total_kiosks_max": 10,
            "company_kiosks_max": 4,
            "removal_ratio_max": 1.00,
            "zip_score_min": 30,
            "zip_score_max": 0,
            "color_code": "#eab308",
            "active": 1,
        },
        {
            "rule_name": "CSV Red Hold",
            "zone_label": "Red",
            "priority": 100,
            "population_min": 0,
            "population_max": 9999,
            "density_min": 0,
            "density_max": 0,
            "competitor_min": 0,
            "competitor_max": 0,
            "total_kiosks_min": 0,
            "total_kiosks_max": 0,
            "company_kiosks_max": 0,
            "removal_ratio_max": 0,
            "zip_score_min": 0,
            "zip_score_max": 0,
            "color_code": "#dc2626",
            "active": 1,
        },
    ]

    existing = {row.rule_name: row for row in (cfg.rules or [])}
    cfg.set("rules", [])
    for row in rules:
        child = existing.get(row["rule_name"]) or {}
        cfg.append("rules", {**child, **row})

    cfg.enabled = 1
    cfg.batch_size = cfg.batch_size or 100
    cfg.run_every_minutes = cfg.run_every_minutes or 15
    cfg.save(ignore_permissions=True)
    frappe.db.commit()
    return {"rules": [row["rule_name"] for row in rules]}


def seed_from_csv_and_refresh(path=CSV_PATH, limit=0, refresh_limit=0):
    seeded = seed_zip_analytics_from_csv(path=path, limit=limit)
    rules = seed_rules_from_csv()

    refreshed = 0
    for idx, (_, zip_code) in enumerate(_read_csv(path), start=1):
        if refresh_limit and idx > int(refresh_limit):
            break
        refresh_zip_record(zip_code)
        refreshed += 1

    frappe.db.commit()
    return {"seeded": seeded, "rules": rules, "refreshed": refreshed}
