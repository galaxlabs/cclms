# cclms/services/zipintel/rules.py
import frappe

def _f(v):
    try:
        if v in (None, ""):
            return None
        return float(v)
    except Exception:
        return None

def _max_or_none(v):
    """Treat 0 (or blank) as 'no maximum'."""
    x = _f(v)
    if x is None:
        return None
    return None if x == 0 else x

def _min_or_none(v):
    """Min=0 is valid; blank means ignore."""
    return _f(v)

def get_criteria():
    return frappe.get_single("ATM Criteria")

def get_active_rules():
    criteria = get_criteria()
    rules = [r for r in (criteria.rules or []) if int(r.active or 0) == 1]
    rules.sort(key=lambda r: int(r.priority or 0), reverse=True)
    return rules

def rule_matches(rule, zip_row):
    reasons = []

    pop = float(zip_row.get("population") or 0)
    dens = float(zip_row.get("population_density") or 0)
    comp = float(zip_row.get("competitor_kiosks") or 0)
    company = float(zip_row.get("company_kiosks") or 0)
    total = float(zip_row.get("total_kiosks") or (comp + company) or 0)
    score = float(zip_row.get("zip_score") or 0)

    installed = float(zip_row.get("kiosks_installed") or 0)
    removed = float(zip_row.get("kiosks_removed") or 0)
    pending = float(zip_row.get("kiosks_pending_removal") or 0)
    denom = max(1.0, installed + removed + pending)
    removal_ratio = removed / denom

    # mins
    pop_min = _min_or_none(getattr(rule, "population_min", None))
    dens_min = _min_or_none(getattr(rule, "density_min", None))
    comp_min = _min_or_none(getattr(rule, "competitor_min", None))
    total_min = _min_or_none(getattr(rule, "total_kiosks_min", None))
    score_min = _min_or_none(getattr(rule, "zip_score_min", None))

    # maxs (0 means ignore)
    pop_max = _max_or_none(getattr(rule, "population_max", None))
    dens_max = _max_or_none(getattr(rule, "density_max", None))
    comp_max = _max_or_none(getattr(rule, "competitor_max", None))
    total_max = _max_or_none(getattr(rule, "total_kiosks_max", None))
    score_max = _max_or_none(getattr(rule, "zip_score_max", None))
    company_max = _max_or_none(getattr(rule, "company_kiosks_max", None))
    removal_max = _max_or_none(getattr(rule, "removal_ratio_max", None))

    # Evaluate
    if pop_min is not None and pop < pop_min: return False, [f"population {pop} < {pop_min}"]
    if pop_max is not None and pop > pop_max: return False, [f"population {pop} > {pop_max}"]

    if dens_min is not None and dens < dens_min: return False, [f"density {dens} < {dens_min}"]
    if dens_max is not None and dens > dens_max: return False, [f"density {dens} > {dens_max}"]

    if comp_min is not None and comp < comp_min: return False, [f"competitor {comp} < {comp_min}"]
    if comp_max is not None and comp > comp_max: return False, [f"competitor {comp} > {comp_max}"]

    if total_min is not None and total < total_min: return False, [f"total_kiosks {total} < {total_min}"]
    if total_max is not None and total > total_max: return False, [f"total_kiosks {total} > {total_max}"]

    if company_max is not None and company > company_max: return False, [f"company_kiosks {company} > {company_max}"]

    if score_min is not None and score < score_min: return False, [f"zip_score {score} < {score_min}"]
    if score_max is not None and score > score_max: return False, [f"zip_score {score} > {score_max}"]

    if removal_max is not None and removal_ratio > removal_max:
        return False, [f"removal_ratio {removal_ratio:.3f} > {removal_max}"]

    # prevent empty rules matching everything
    has_any = any(x is not None for x in [
        pop_min, pop_max, dens_min, dens_max,
        comp_min, comp_max, total_min, total_max,
        company_max, score_min, score_max, removal_max
    ])
    if not has_any:
        return False, ["rule has no constraints"]

    return True, ["matched"]

def classify_zip_row(zip_row):
    debug = []
    for r in get_active_rules():
        matched, why = rule_matches(r, zip_row)
        debug.append({"rule": r.rule_name, "zone": r.zone_label, "matched": matched, "why": why})
        if matched:
            return (r.zone_label, r.rule_name, debug)
    return ("Unknown", None, debug)

@frappe.whitelist()
def test_zip(zip_code: str):
    zip_code = str(zip_code).zfill(5)
    row = frappe.db.get_value("Zip Code Analytics", {"zip_code": zip_code}, "*", as_dict=True)
    if not row:
        return {"ok": False, "msg": "ZIP not found", "zip_code": zip_code}
    zone, rule, debug = classify_zip_row(row)
    return {"ok": True, "zip_code": zip_code, "zone": zone, "matched_rule": rule, "debug": debug}

# import frappe

# def classify_zip(zip_code: str):
#     """Return (zone_name, color_code) based on active ATM Criteria Rule Sets."""
#     zip_data = frappe.db.get_value(
#         "Zip Code Analytics",
#         {"zip_code": str(zip_code).zfill(5)},
#         ["population", "kiosks_installed", "kiosks_removed",
#          "population_density", "margin", "total_kiosks", "company_kiosks"],
#         as_dict=True,
#     )
#     if not zip_data:
#         return "Unknown", "#9ca3af"

#     # calculate derived metrics
#     installed = zip_data.kiosks_installed or 0
#     removed = zip_data.kiosks_removed or 0
#     zip_data["removal_ratio"] = (removed / (installed or 1)) if (installed or removed) else 0.0
#     zip_data["competitor_kiosks"] = max((zip_data.get("total_kiosks") or 0) - (zip_data.get("company_kiosks") or 0), 0)

#     # iterate through active rule sets
#     rules = frappe.get_all(
#         "ATM Criteria Rule Set",
#         filters={"active": 1},
#         fields="*",
#         order_by="priority asc",
#     )

#     for r in rules:
#         if (
#             zip_data["population"] >= (r.population_min or 0)
#             and (not r.population_max or zip_data["population"] <= r.population_max)
#             and zip_data["margin"] >= (r.margin_min or 0)
#             and zip_data["population_density"] >= (r.density_min or 0)
#             and (not r.density_max or zip_data["population_density"] <= r.density_max)
#             and zip_data["removal_ratio"] <= (r.removal_ratio_max or 1)
#             and zip_data["competitor_kiosks"] <= (r.competitor_max or 99)
#         ):
#             return r.rule_name, r.color_code

#     return "Unclassified", "#9ca3af"
