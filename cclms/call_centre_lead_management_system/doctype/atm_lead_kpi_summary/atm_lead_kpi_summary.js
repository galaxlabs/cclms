// Copyright (c) 2025, Galaxy and contributors
// For license information, please see license.txt

// frappe.ui.form.on("ATM Lead KPI Summary", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('ATM Lead KPI Summary', {
    refresh(frm) {
        if (!frm.doc.__islocal) {
            // Rebuild KPI rows
            frm.add_custom_button(__('Rebuild KPI Rows'), () => {
                frm.call('rebuild_rows').then(() => {
                    frm.reload_doc();
                });
            });

            // Apply closer adjustments
            frm.add_custom_button(__('Apply Closer Adjustments'), () => {
                frm.call('apply_transfers').then(() => {
                    frm.reload_doc();
                });
            });
        }
    }
});

