import frappe

@frappe.whitelist()
def run_update_competitor_density():
    return frappe.get_attr("cclms.api.competitors.update_competitor_density")()

@frappe.whitelist()
def run_update_totals():
    return frappe.get_attr("cclms.api.competitors.update_totals_from_company_vs_competitors")()

@frappe.whitelist()
def run_apply_rules():
    return frappe.get_attr("cclms.api.zip_rules.apply_rule_sets_to_zips")()

@frappe.whitelist()
def run_refresh_competitors_around_zip(zip_code: str, km: float = 25.0, force: int = 1):
    return frappe.get_attr("cclms.api.competitors.refresh_competitors_around_zip")(zip_code, km, force)


@frappe.whitelist()
def run_backfill_kiosk_actual_zip(limit: int = 20000, rate_ms: int = 300):
    return frappe.get_attr("cclms.api.competitors.backfill_kiosk_actual_zip")(limit=limit, rate_ms=rate_ms)

# Optional async versions (enqueue background jobs)
@frappe.whitelist()
def enqueue_update_density_and_totals():
    frappe.enqueue("cclms.api.competitors.update_competitor_density", queue="long")
    frappe.enqueue("cclms.api.competitors.update_totals_from_company_vs_competitors", queue="long")
    return {"enqueued": True}
