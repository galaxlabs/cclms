frappe.ui.form.on("Device Profile", {
    refresh(frm) {
        if (frm.is_new()) {
            return;
        }

        frm.add_custom_button(__("Open Tracker Device"), () => {
            const target = frm.doc.tracker_device || frm.doc.device_id;
            if (target) {
                frappe.set_route("Form", "Tracker Device", target);
            }
        }, __("Links"));

        frm.add_custom_button(__("Reset Desk Password"), () => {
            const dialog = new frappe.ui.Dialog({
                title: __("Reset Tracked User Password"),
                fields: [
                    {
                        fieldtype: "Data",
                        fieldname: "new_password",
                        label: __("New Password"),
                        description: __("Leave blank to auto-generate a secure password."),
                    },
                ],
                primary_action_label: __("Reset Password"),
                primary_action(values) {
                    frappe.call({
                        method: "cclms.api.device_profile_admin.reset_profile_user_password",
                        args: {
                            name: frm.doc.name,
                            new_password: values.new_password || null,
                        },
                        callback: function (r) {
                            const message = r.message || {};
                            frappe.msgprint({
                                title: __("Desk Password Reset"),
                                message: __("Tracked user: {0}<br>New password: <b>{1}</b>", [
                                    message.tracked_user || "",
                                    message.new_password || "",
                                ]),
                                indicator: "orange",
                            });
                            frm.reload_doc();
                        },
                    });
                    dialog.hide();
                },
            });
            dialog.show();
        }, __("Security"));

        if ((frm.doc.status || "Active") === "Blocked") {
            frm.add_custom_button(__("Unblock Device"), () => {
                frappe.prompt(
                    [{ fieldtype: "Small Text", fieldname: "note", label: __("Note") }],
                    (values) => {
                        frappe.call({
                            method: "cclms.api.device_profile_admin.unblock_device_profile",
                            args: { name: frm.doc.name, note: values.note || null },
                            callback: () => frm.reload_doc(),
                        });
                    },
                    __("Unblock Device Profile"),
                    __("Unblock")
                );
            }, __("Security"));
        } else {
            frm.add_custom_button(__("Block Device"), () => {
                frappe.prompt(
                    [{ fieldtype: "Small Text", fieldname: "reason", label: __("Reason"), reqd: 1 }],
                    (values) => {
                        frappe.call({
                            method: "cclms.api.device_profile_admin.block_device_profile",
                            args: { name: frm.doc.name, reason: values.reason },
                            callback: () => frm.reload_doc(),
                        });
                    },
                    __("Block Device Profile"),
                    __("Block")
                );
            }, __("Security"));
        }
    },
});
