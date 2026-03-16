// Copyright (c) 2026, Galaxy and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Ops Maintenance", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Ops Maintenance', {
  refresh(frm) {
    if (frm.is_new()) return;

    frm.clear_custom_buttons();

    const grp = __('Rebuild');

    frm.add_custom_button(__('Rebuild Deals Since Cutoff'), () => {
      const cutoff = frm.doc.cutoff_date || '2025-08-01';
      frappe.confirm(
        `Rebuild Operator/Location/Deals from ATM Leads created/modified on or after ${cutoff}?`,
        () => frm.call('rebuild_deals_since_cutoff').then(() => frm.reload_doc())
      );
    }, grp);

    frm.add_custom_button(__('Backfill Dates From State History'), () => {
      frappe.confirm(
        `Fill missing milestone dates in Operator Deal from ATM Lead State History?`,
        () => frm.call('backfill_dates_from_state_history').then(() => frm.reload_doc())
      );
    }, grp);
  }
});
