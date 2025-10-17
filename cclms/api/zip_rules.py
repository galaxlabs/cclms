import frappe
from frappe.utils import now_datetime

def _num(x, kind="int"):
    try:
        return int(float(x)) if kind=="int" else float(x)
    except:
        return 0 if kind=="int" else 0.0

def _in_range(v, vmin, vmax):
    if vmin is not None and v < vmin: return False
    if vmax is not None and v > vmax: return False
    return True

@frappe.whitelist()
def apply_rule_sets_to_zips():
    """
    Evaluate ATM Criteria Rule Set against Zip Code Analytics.
    - First matching active rule (by ascending priority) wins
    - Sets zone_color (from rule.color_code or name bucket)
    - Computes a simple zip_score (signal): +1 for each '+' condition and -1 for each '-' hit
    """
    # load rules (active only), order by priority
    rules = frappe.get_all(
        "ATM Criteria Rule Set",
        fields=["name","rule_name","priority","active","color_code",
                "population_min","population_max",
                "margin_min","margin_max",
                "density_min","density_max",
                "removal_ratio_max","competitor_max"],
        filters={"active": 1},
        order_by="priority asc"
    )

    zips = frappe.get_all("Zip Code Analytics",
                          fields=["name","zip_code","population","margin",
                                  "population_density","removal_rate",
                                  "competitor_density","company_kiosks","kiosks_installed","kiosks_removed"],
                          limit_page_length=200000)

    updated = 0
    for z in zips:
        pop  = _num(z.get("population"), "int")
        mar  = _num(z.get("margin"), "float")
        dens = _num(z.get("population_density"), "float")
        rem  = _num(z.get("removal_rate"), "float")
        comp = _num(z.get("competitor_density"), "int")

        chosen_color = None
        score = 0  # signal

        for r in rules:
            ok  = _in_range(pop,  r.get("population_min"), r.get("population_max"))
            ok &= _in_range(mar,  r.get("margin_min"),     r.get("margin_max"))
            ok &= _in_range(dens, r.get("density_min"),    r.get("density_max"))
            if r.get("removal_ratio_max") is not None and rem > r.get("removal_ratio_max"):
                ok = False
            if r.get("competitor_max") is not None and comp > r.get("competitor_max"):
                ok = False

            if ok:
                # color from rule; if empty, map by rule name
                chosen_color = r.get("color_code") or _fallback_color(r["rule_name"])
                # build a simple signal: higher margin/pop/density = + ; higher removal/competitors = -
                score = 0
                if r.get("margin_min") is not None and mar >= r["margin_min"]: score += 1
                if r.get("population_min") is not None and pop >= r["population_min"]: score += 1
                if r.get("density_min") is not None and dens >= r["density_min"]: score += 1
                if r.get("removal_ratio_max") is not None and rem <= r["removal_ratio_max"]: score += 1
                if r.get("competitor_max") is not None and comp <= r["competitor_max"]: score += 1
                break

        # default if no rule matched
        if not chosen_color:
            chosen_color = "Red"
            score = 0

        frappe.db.set_value("Zip Code Analytics", z["name"], {
            "zone_color": chosen_color,
            "zip_score": float(score),
            "last_score_update": now_datetime()
        })
        updated += 1

    frappe.db.commit()
    return {"updated": updated, "rules": len(rules)}

def _fallback_color(rule_name: str):
    nm = (rule_name or "").lower()
    if "green" in nm and "light" not in nm: return "Green"
    if "light" in nm: return "Light Green"
    if "yellow" in nm: return "Yellow"
    return "Red"
