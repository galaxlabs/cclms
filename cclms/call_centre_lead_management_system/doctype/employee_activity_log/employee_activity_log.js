frappe.ui.form.on("Employee Activity Log", {
    refresh(frm) {
        if (frm.doc.device_profile) {
            frm.add_custom_button(__("Open Device Profile"), () => {
                frappe.set_route("Form", "Device Profile", frm.doc.device_profile);
            }, __("Connections"));
        }

        if (frm.doc.tracker_device) {
            frm.add_custom_button(__("Open Tracker Device"), () => {
                frappe.set_route("Form", "Tracker Device", frm.doc.tracker_device);
            }, __("Connections"));
        }
    },
});
