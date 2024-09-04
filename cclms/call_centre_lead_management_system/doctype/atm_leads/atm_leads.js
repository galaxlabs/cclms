// Copyright (c) 2024, Galaxy and contributors
// For license information, please see license.txt

// frappe.ui.form.on("ATM Leads", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('ATM Leads', {
    validate: function(frm) {
        // Check if the company field is selected
        if (frm.doc.company) {
            // Fetch permitted states from the child table of the selected company
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Permitted States", // Child Doctype name
                    filters: {
                        'parent': frm.doc.company // Parent field linking to the selected company
                    },
                    fields: ['state', 'state_code'] // Fields to retrieve for validation
                },
                async: false, // Ensure call completes before continuing
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        // List of permitted states retrieved from the operator's child table
                        let permitted_states = r.message;

                        // Check if lead's state or state code matches any permitted state
                        let is_permitted = permitted_states.some(function(d) {
                            return (d.state === frm.doc.state) ||
                                   (d.state_code === frm.doc.state_code);
                        });

                        // If no match found, block the save/submit
                        if (!is_permitted) {
                            frappe.validated = false; // Prevent form submission
                            frappe.msgprint({
                                title: __('Not Qualified'),
                                message: __('This lead is not qualified for the selected operator because the state or state code is not permitted.'),
                                indicator: 'red'
                            });
                        }
                    } else {
                        // If no permitted states are found for the company, prevent form submission
                        frappe.validated = false;
                        frappe.msgprint({
                            title: __('Validation Error'),
                            message: __(),
                            indicator: 'red'
                        });
                    }
                }
            });
        } else {
            // If company is not selected, also prevent form submission
            frappe.validated = false;
            frappe.msgprint({
                title: __('Company Not Selected'),
                message: __('Please select a company before saving the lead.'),
                indicator: 'red'
            });
        }
    }
});
