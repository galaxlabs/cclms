// Copyright (c) 2024, Galaxy and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Old Leads", {
// 	refresh(frm) {

// 	},
// });
// frappe.ui.form.on('Old Leads', {
//     refresh: function(frm) {
//         // Add a custom button to convert to ATM Lead
//         frm.add_custom_button(__('Convert to ATM Lead'), function() {
//             // Check if the lead_status is not "Draft"
//             if (frm.doc.lead_status !== 'Draft') {

//                 // Define the filters for duplicate checking
//                 let filters = {
//                     address: frm.doc.address,
//                     city: frm.doc.city,
//                     zippostal_code: frm.doc.zippostal_code,
//                     state: frm.doc.state,
//                     business_name: frm.doc.business_name,
//                     company: frm.doc.company
//                 };

//                 // First, check for duplicates in ATM Leads
//                 frappe.call({
//                     method: 'frappe.client.get_list',
//                     args: {
//                         doctype: 'ATM Leads',
//                         filters: filters,
//                         fields: ['name', 'post_date', 'is_duplicate', 'branch']
//                     },
//                     callback: function(atm_response) {
//                         let atm_lead_duplicates = atm_response.message;

//                         if (atm_lead_duplicates.length > 0) {
//                             let atm_lead = atm_lead_duplicates[0]; // Assuming one duplicate for simplicity
                            
//                             // Compare post_date to decide action
//                             let atm_post_date = new Date(atm_lead.post_date);
//                             let old_post_date = new Date(frm.doc.post_date);
                            
//                             if (atm_post_date > old_post_date) {
//                                 // If ATM Lead has a newer date, create a new ATM Lead
//                                 createATMLead(frm, true); // Create new ATM Lead
//                             } else {
//                                 // If ATM Lead has an older or equal post_date, mark as duplicate and add comment
//                                 frappe.call({
//                                     method: 'frappe.client.set_value',
//                                     args: {
//                                         doctype: 'ATM Leads',
//                                         name: atm_lead.name,
//                                         fieldname: 'is_duplicate',
//                                         value: 1 // Marking it as duplicate
//                                     },
//                                     callback: function(r) {
//                                         if (!r.exc) {
//                                             // Add a comment with the reference to the Old Lead and branch
//                                             frappe.call({
//                                                 method: 'frappe.model.add_comment',
//                                                 args: {
//                                                     reference_doctype: 'ATM Leads',
//                                                     reference_name: atm_lead.name,
//                                                     content: `Duplicate Lead found from Old Lead ${frm.doc.name} in branch ${frm.doc.branch}.`
//                                                 },
//                                                 callback: function() {
//                                                     frappe.msgprint(__('Duplicate Lead found. Marked as duplicate in ATM Leads and comments updated.'));
//                                                 }
//                                             });
//                                         }
//                                     }
//                                 });
//                             }
//                         } else {
//                             // No duplicates found, create new ATM Lead
//                             createATMLead(frm, false); // Create new ATM Lead
//                         }
//                     }
//                 });
//             } else {
//                 frappe.msgprint(__('Lead is in Draft status. Conversion not allowed.'));
//             }
//         });
//     }
// });

// function createATMLead(frm, checkForCompanyAndBusinessType) {
//     let business_type = frm.doc.business_type;

//     // Fix spelling issues by capitalizing the first letter of business_type
//     business_type = business_type.charAt(0).toUpperCase() + business_type.slice(1).toLowerCase();

//     let company = frm.doc.company;

//     // Check if company or business_type exists, if not, create a new entry for business_type
//     if (checkForCompanyAndBusinessType) {
//         frappe.db.exists('Operator Companies', company).then(exists => {
//             if (!exists) {
//                 // Create a new company if it doesn't exist
//                 frappe.call({
//                     method: 'frappe.client.insert',
//                     args: {
//                         doc: {
//                             doctype: 'Operator Companies',
//                             company_name: company
//                         }
//                     }
//                 });
//             }
//         });

//         frappe.db.exists('Business Types', business_type).then(exists => {
//             if (!exists) {
//                 // Create a new business_type if it doesn't exist
//                 frappe.call({
//                     method: 'frappe.client.insert',
//                     args: {
//                         doc: {
//                             doctype: 'Business Types',
//                             business_type: business_type
//                         }
//                     }
//                 });
//             }
//         });
//     }

//     // Set current logged-in employee as the default if no match found
//     let current_employee = frappe.session.user;

//     // Create the new ATM Lead
//     frappe.call({
//         method: 'frappe.client.insert',
//         args: {
//             doc: {
//                 doctype: 'ATM Leads',
//                 company: frm.doc.company,
//                 lead_status: frm.doc.lead_status,
//                 business_name: frm.doc.business_name,
//                 owner_name: frm.doc.owner_name,
//                 address: frm.doc.address,
//                 zippostal_code: frm.doc.zippostal_code,
//                 state: frm.doc.state,
//                 state_code:frm.doc.state_code,
//                 city: frm.doc.city,
//                 country: frm.doc.country,
//                 executive_name: frm.doc.executive_name || current_employee,
//                 sales_person: frm.doc.sales_person,
//                 branch: frm.doc.branch,
//                 email: frm.doc.email,
//                 business_phone_number: frm.doc.business_phone_number,
//                 personal_cell_phone: frm.doc.personal_cell_phone,
//                 contract_length: frm.doc.contract_length,
//                 percentage: frm.doc.percentage,
//                 base_rent: frm.doc.base_rent,
//                 hours: frm.doc.hours,
//                 approve_date: frm.doc.approve_date,
//                 agreement_sent_date: frm.doc.agreement_sent_date,
//                 sign_date: frm.doc.sign_date,
//                 install_date: frm.doc.install_date,
//                 business_type: business_type // Set fixed business_type
//             }
//         },
//         callback: function(r) {
//             if (!r.exc) {
//                 frappe.msgprint(__('New ATM Lead created successfully.'));

//                 // Delete the old lead after successful creation of the new ATM Lead
//                 frappe.call({
//                     method: 'frappe.client.delete',
//                     args: {
//                         doctype: 'Old Leads',
//                         name: frm.doc.name
//                     },
//                     callback: function() {
//                         frappe.msgprint(__('Old Lead record deleted successfully.'));
//                     }
//                 });
//             }
//         }
//     });
// }
