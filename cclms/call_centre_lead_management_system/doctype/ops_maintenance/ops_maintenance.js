frappe.ui.form.on("Ops Maintenance", {
  refresh(frm) {
    if (frm.is_new()) {
      return;
    }

    frm.clear_custom_buttons();
    const group = __("Maintenance");

    frm.add_custom_button(__("Rebuild Deals Since Cutoff"), () => {
      frappe.confirm(
        __("Rebuild Operator, BTM Location, and Operator Deal rows for the current cutoff/batch window?"),
        () => frm.call("rebuild_deals_since_cutoff").then(() => frm.reload_doc())
      );
    }, group);

    frm.add_custom_button(__("Backfill Dates From State History"), () => {
      frappe.confirm(
        __("Backfill milestone dates from ATM Lead State History using DB updates only?"),
        () => frm.call("backfill_dates_from_state_history").then(() => frm.reload_doc())
      );
    }, group);

    frm.add_custom_button(__("Clean Enrich From ZIP Analytics"), () => {
      frappe.confirm(
        __("Refresh Operator Deal enrichment fields from Zip Code Analytics for the current batch?"),
        () => frm.call("clean_enrich_from_zip_analytics").then(() => frm.reload_doc())
      );
    }, group);

    frm.add_custom_button(__("AI Enrichment"), () => {
      frappe.confirm(
        __("Run low-volume AI enrichment for the current batch using local-first policy?"),
        () => frm.call("ai_enrichment").then(() => frm.reload_doc())
      );
    }, group);
  }
});
