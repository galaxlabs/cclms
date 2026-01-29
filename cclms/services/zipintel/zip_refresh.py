import frappe
from frappe.utils import now_datetime

# ---------------------------
# Helpers
# ---------------------------
def _z5(z):
    return str(z or "").zfill(5)

def _num(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default

def _max_or_none(v):
    """Interpret 0 or empty as 'no max'."""
    v = _num(v, 0)
    return None if v <= 0 else v

def _min_or_none(v):
    """Interpret 0 or empty as 'no min'."""
    v = _num(v, 0)
    return None if v <= 0 else v

def _doctype_has_field(doctype: str, fieldname: str) -> bool:
    meta = frappe.get_meta(doctype)
    return any(f.fieldname == fieldname for f in meta.fields)

# ---------------------------
# Rules (read from Single: ATM Criteria)
# ---------------------------
def get_rules_from_single():
    cfg = frappe.get_single("ATM Criteria")
    rules = []
    for r in (cfg.get("rules") or []):
        if not int(r.get("active") or 0):
            continue
        rules.append(r)

    # priority high -> first
    rules.sort(key=lambda x: int(x.get("priority") or 0), reverse=True)
    return cfg, rules

def rule_matches(rule: dict, z: dict):
    """
    Your rule fields (from your JSON):
      density_min/density_max
      competitor_min/competitor_max
      total_kiosks_min/total_kiosks_max
      population_min/population_max
      removal_ratio_max
      zip_score_min/zip_score_max
      company_kiosks_max
      zone_label (Green/Light Green/Yellow/Red)
      rule_name
    """

    pop = _num(z.get("population"))
    dens = _num(z.get("population_density"))
    comp = _num(z.get("competitor_kiosks"))
    total = _num(z.get("total_kiosks"))
    company = _num(z.get("company_kiosks"))
    score = _num(z.get("zip_score"))

    installed = _num(z.get("kiosks_installed"))
    removed = _num(z.get("kiosks_removed"))
    pending = _num(z.get("kiosks_pending_removal"))
    denom = max(1.0, installed + removed + pending)
    removal_ratio = (removed / denom) if denom else 0.0

    # mins
    pop_min = _min_or_none(rule.get("population_min"))
    dens_min = _min_or_none(rule.get("density_min"))
    comp_min = _min_or_none(rule.get("competitor_min"))
    total_min = _min_or_none(rule.get("total_kiosks_min"))
    score_min = _min_or_none(rule.get("zip_score_min"))

    # max (0 means unlimited)
    pop_max = _max_or_none(rule.get("population_max"))
    dens_max = _max_or_none(rule.get("density_max"))
    comp_max = _max_or_none(rule.get("competitor_max"))
    total_max = _max_or_none(rule.get("total_kiosks_max"))
    score_max = _max_or_none(rule.get("zip_score_max"))
    removal_max = _max_or_none(rule.get("removal_ratio_max"))
    company_max = _max_or_none(rule.get("company_kiosks_max"))

    if pop_min is not None and pop < pop_min: return False
    if pop_max is not None and pop > pop_max: return False

    if dens_min is not None and dens < dens_min: return False
    if dens_max is not None and dens > dens_max: return False

    if comp_min is not None and comp < comp_min: return False
    if comp_max is not None and comp > comp_max: return False

    if total_min is not None and total < total_min: return False
    if total_max is not None and total > total_max: return False

    if score_min is not None and score < score_min: return False
    if score_max is not None and score > score_max: return False

    if removal_max is not None and removal_ratio > removal_max: return False

    if company_max is not None and company > company_max: return False

    # avoid “empty rule matches everything”
    has_any_threshold = any([
        pop_min, pop_max, dens_min, dens_max, comp_min, comp_max,
        total_min, total_max, score_min, score_max, removal_max, company_max
    ])
    if not has_any_threshold:
        return False

    return True

def classify_zone(zip_row: dict, rules: list):
    for r in rules:
        if rule_matches(r, zip_row):
            return (r.get("zone_label") or r.get("rule_name") or "Unknown", r.get("rule_name") or r.get("name"))
    return ("Unknown", None)

# ---------------------------
# Batch: cursor-based refresh
# ---------------------------
def _get_next_zip_batch(cursor_zip: str, batch_size: int):
    cursor_zip = _z5(cursor_zip)

    rows = frappe.get_all(
        "Zip Code Analytics",
        fields=[
            "name", "zip_code", "population", "population_density",
            "land_sq_mi", "square_miles",
            "kiosks_installed", "kiosks_removed", "kiosks_pending_removal",
            "zip_score", "margin",
            "company_kiosks", "competitor_kiosks", "total_kiosks",
        ],
        filters={"zip_code": [">", cursor_zip]},
        order_by="zip_code asc",
        limit_page_length=int(batch_size),
    )

    # wrap-around if end reached
    if not rows:
        rows = frappe.get_all(
            "Zip Code Analytics",
            fields=[
                "name", "zip_code", "population", "population_density",
                "land_sq_mi", "square_miles",
                "kiosks_installed", "kiosks_removed", "kiosks_pending_removal",
                "zip_score", "margin",
                "company_kiosks", "competitor_kiosks", "total_kiosks",
            ],
            order_by="zip_code asc",
            limit_page_length=int(batch_size),
        )

    for r in rows:
        r["zip_code"] = _z5(r.get("zip_code"))
    return rows

def _counts_by_zip(doctype: str, zip_field: str, zip_list: list, extra_filters=None):
    """
    Efficient grouped count query.
    """
    extra_filters = extra_filters or []
    placeholders = ", ".join(["%s"] * len(zip_list))

    where = [f"`{zip_field}` IN ({placeholders})"]
    values = list(zip_list)

    # extra_filters items: ("field", "op", "value")
    for f, op, v in extra_filters:
        where.append(f"`{f}` {op} %s")
        values.append(v)

    table = f"`tab{doctype}`"
    sql = f"""
        SELECT `{zip_field}` as zip_code, COUNT(*) as cnt
        FROM {table}
        WHERE {" AND ".join(where)}
        GROUP BY `{zip_field}`
    """
    data = frappe.db.sql(sql, values=values, as_dict=True)
    out = {_z5(d["zip_code"]): int(d["cnt"]) for d in data if d.get("zip_code")}
    return out

@frappe.whitelist()
def refresh_zip_analytics_batch(batch_size: int = None):
    """
    Runs ONE small batch and updates:
      competitor_kiosks, company_kiosks, total_kiosks,
      densities, removal_rate,
      zone_color, matched_rule, zone_updated_on,
      and cursor in ATM Criteria.
    """
    cfg, rules = get_rules_from_single()
    if not int(cfg.get("enabled") or 0):
        return {"ok": False, "msg": "ATM Criteria is disabled"}

    bs = int(batch_size or cfg.get("batch_size") or 100)
    cursor = _z5(cfg.get("last_zip_cursor") or "00000")

    batch = _get_next_zip_batch(cursor, bs)
    if not batch:
        return {"ok": False, "msg": "No ZIP rows found"}

    zip_list = [b["zip_code"] for b in batch]

    # 1) competitor kiosks
    comp_map = _counts_by_zip("Competitor Kiosk", "zip_code", zip_list)

    # 2) company kiosks from ATM Leads (zip field differs)
    # If ATM Leads has field zippostal_code, use it; else fallback to zip_code
    atm_zip_field = "zip_code" if _doctype_has_field("ATM Leads", "zip_code") else "zip_code"

    # Optional: filter only installed leads if you have such statuses
    # If you want this stricter, add a config field later. For now: count all.
    company_map = _counts_by_zip("ATM Leads", atm_zip_field, zip_list)

    updated = 0
    now = now_datetime()

    for z in batch:
        zc = z["zip_code"]

        competitor = int(comp_map.get(zc, 0))
        company = int(company_map.get(zc, 0))

        land = _num(z.get("land_sq_mi"), 0) or _num(z.get("square_miles"), 0)
        land = land if land > 0 else 0.0

        total = company + competitor

        # densities (simple)
        competitor_density = (competitor / land) if land else 0.0
        kiosk_density_company = (company / land) if land else 0.0
        kiosk_density_total = (total / land) if land else 0.0

        pop = _num(z.get("population"), 0.0)
        kiosk_penetration_pct = (total / pop * 100.0) if pop else 0.0

        installed = _num(z.get("kiosks_installed"))
        removed = _num(z.get("kiosks_removed"))
        pending = _num(z.get("kiosks_pending_removal"))
        denom = max(1.0, installed + removed + pending)
        removal_rate = (removed / denom * 100.0) if denom else 0.0

        # update in-memory row used by rules
        z_calc = dict(z)
        z_calc.update({
            "competitor_kiosks": competitor,
            "company_kiosks": company,
            "total_kiosks": total,
        })

        zone, matched_rule = classify_zone(z_calc, rules)

        frappe.db.set_value("Zip Code Analytics", z["name"], {
            "competitor_kiosks": competitor,
            "company_kiosks": company,
            "total_kiosks": total,
            "competitor_density": competitor_density,
            "kiosk_density_company": kiosk_density_company,
            "kiosk_density_total": kiosk_density_total,
            "kiosk_penetration_pct": kiosk_penetration_pct,
            "removal_rate": removal_rate,
            "zone_color": zone if zone in ("Green", "Light Green", "Yellow", "Red") else "Red",
            "matched_rule": matched_rule or "",
            "zone_updated_on": now,
            "last_score_update": now,
        })
        updated += 1

    # move cursor to the last processed zip
    new_cursor = batch[-1]["zip_code"]
    cfg.db_set("last_zip_cursor", new_cursor)

    frappe.db.commit()
    return {"ok": True, "updated": updated, "cursor_from": cursor, "cursor_to": new_cursor}
