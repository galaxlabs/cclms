frappe.ui.form.on("Tracker Device", {
    refresh(frm) {
        if (frm.is_new()) {
            return;
        }

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
                        method: "cclms.api.tracker_admin.reset_tracked_user_password",
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

        if (Number(frm.doc.active || 0) === 1) {
            frm.add_custom_button(__("Block Device"), () => {
                frappe.prompt(
                    [
                        {
                            fieldtype: "Small Text",
                            fieldname: "reason",
                            label: __("Reason"),
                            reqd: 1,
                        },
                    ],
                    (values) => {
                        frappe.call({
                            method: "cclms.api.tracker_admin.block_tracker_device",
                            args: { name: frm.doc.name, reason: values.reason },
                            callback: () => frm.reload_doc(),
                        });
                    },
                    __("Block Tracker Device"),
                    __("Block")
                );
            }, __("Security"));
        } else {
            frm.add_custom_button(__("Unblock Device"), () => {
                frappe.prompt(
                    [
                        {
                            fieldtype: "Small Text",
                            fieldname: "note",
                            label: __("Note"),
                        },
                    ],
                    (values) => {
                        frappe.call({
                            method: "cclms.api.tracker_admin.unblock_tracker_device",
                            args: { name: frm.doc.name, note: values.note || null },
                            callback: () => frm.reload_doc(),
                        });
                    },
                    __("Unblock Tracker Device"),
                    __("Unblock")
                );
            }, __("Security"));
        }
    },
});
