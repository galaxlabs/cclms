// Copyright (c) 2025, Galaxy and contributors
// For license information, please see license.txt

// frappe.ui.form.on("ATM Lead KPI Summary", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('ATM Lead KPI Summary', {
    refresh: function (frm) {
        // For new docs, do nothing
        if (frm.is_new()) {
            return;
        }

        // Optional: clear previous indicators
        frm.dashboard.clear_headline();

        // Safely read values (avoid undefined)
        var posted = frm.doc.leads_posted || 0;
        var approved = frm.doc.leads_approved || 0;
        var signed = frm.doc.leads_signed || 0;
        var converted = frm.doc.leads_converted || 0;
        var installed = frm.doc.leads_installed || 0;
        var removed = frm.doc.leads_removed || 0;
        var rejected = frm.doc.leads_sign_rejected || 0;
        var avg_approval = frm.doc.avg_approval_days || 0;
        var avg_sign = frm.doc.avg_sign_days || 0;

        frm.dashboard.add_indicator(
            __('Submitted: {0}', [posted]),
            'blue'
        );
        frm.dashboard.add_indicator(
            __('Approved: {0}', [approved]),
            'green'
        );
        frm.dashboard.add_indicator(
            __('Signed: {0}', [signed]),
            'green'
        );
        frm.dashboard.add_indicator(
            __('Converted: {0}', [converted]),
            'green'
        );
        frm.dashboard.add_indicator(
            __('Installed: {0}', [installed]),
            'green'
        );
        frm.dashboard.add_indicator(
            __('Removed: {0}', [removed]),
            'orange'
        );
        frm.dashboard.add_indicator(
            __('Sign Rejected: {0}', [rejected]),
            'red'
        );
        frm.dashboard.add_indicator(
            __('Avg Approval Days: {0}', [avg_approval]),
            'orange'
        );
        frm.dashboard.add_indicator(
            __('Avg Sign Days: {0}', [avg_sign]),
            'orange'
        );
    }
});
frappe.ui.form.on('ATM Lead KPI Summary', {
    refresh(frm) {
        // only show buttons on saved docs
        if (frm.is_new()) return;

        frm.add_custom_button(__('Rebuild KPI Rows'), function () {
            frm.call('rebuild_rows').then(() => {
                frm.reload_doc();
            });
        });
    }
});

// frappe.ui.form.on('ATM Lead KPI Summary', {
//     refresh(frm) {
//         if (!frm.doc.__islocal) {
//             // Rebuild KPI rows
//             frm.add_custom_button(__('Rebuild KPI Rows'), () => {
//                 frm.call('rebuild_rows').then(() => {
//                     frm.reload_doc();
//                 });
//             });

//             // Apply closer adjustments
//             frm.add_custom_button(__('Apply Closer Adjustments'), () => {
//                 frm.call('apply_transfers').then(() => {
//                     frm.reload_doc();
//                 });
//             });
//         }
//     }
// });

