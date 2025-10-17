// Copyright (c) 2025, Galaxy and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Zip Code Analytics", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Zip Code Analytics', {
  refresh(frm) {
    frm.add_custom_button('Update Competitor Density', () => {
      frappe.call({
        method: 'cclms.api.ops.run_update_competitor_density',
        callback: r => frappe.msgprint(__('Done: {0}', [JSON.stringify(r.message)]))
      });
    });

    frm.add_custom_button('Update Totals', () => {
      frappe.call({
        method: 'cclms.api.ops.run_update_totals',
        callback: r => frappe.msgprint(__('Done: {0}', [JSON.stringify(r.message)]))
      });
    });

    frm.add_custom_button('Apply Rule Sets (Color & Score)', () => {
      frappe.call({
        method: 'cclms.api.ops.run_apply_rules',
        callback: r => frappe.msgprint(__('Done: {0}', [JSON.stringify(r.message)]))
      });
    });

    frm.add_custom_button('Refresh Competitors around this ZIP', () => {
      const z = frm.doc.zip_code;
      if (!z) {
        frappe.msgprint(__('Missing zip_code on this document'));
        return;
      }
      frappe.call({
        method: 'cclms.api.ops.run_refresh_competitors_around_zip',
        args: { zip_code: z, km: 25, force: 1 },
        callback: r => frappe.msgprint(__('Done: {0}', [JSON.stringify(r.message)]))
      });
    });
  }
});
