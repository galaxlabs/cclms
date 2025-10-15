import frappe

def classify_zip(zip_code: str):
    """Return (zone_name, color_code) based on active ATM Criteria Rule Sets."""
    zip_data = frappe.db.get_value(
        "Zip Code Analytics",
        {"zip_code": str(zip_code).zfill(5)},
        ["population", "kiosks_installed", "kiosks_removed",
         "population_density", "margin", "total_kiosks", "company_kiosks"],
        as_dict=True,
    )
    if not zip_data:
        return "Unknown", "#9ca3af"

    # calculate derived metrics
    installed = zip_data.kiosks_installed or 0
    removed = zip_data.kiosks_removed or 0
    zip_data["removal_ratio"] = (removed / (installed or 1)) if (installed or removed) else 0.0
    zip_data["competitor_kiosks"] = max((zip_data.get("total_kiosks") or 0) - (zip_data.get("company_kiosks") or 0), 0)

    # iterate through active rule sets
    rules = frappe.get_all(
        "ATM Criteria Rule Set",
        filters={"active": 1},
        fields="*",
        order_by="priority asc",
    )

    for r in rules:
        if (
            zip_data["population"] >= (r.population_min or 0)
            and (not r.population_max or zip_data["population"] <= r.population_max)
            and zip_data["margin"] >= (r.margin_min or 0)
            and zip_data["population_density"] >= (r.density_min or 0)
            and (not r.density_max or zip_data["population_density"] <= r.density_max)
            and zip_data["removal_ratio"] <= (r.removal_ratio_max or 1)
            and zip_data["competitor_kiosks"] <= (r.competitor_max or 99)
        ):
            return r.rule_name, r.color_code

    return "Unclassified", "#9ca3af"
