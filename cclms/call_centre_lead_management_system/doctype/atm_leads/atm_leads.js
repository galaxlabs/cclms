// Copyright (c) 2024, Galaxy and contributors
// For license information, please see license.txt

// frappe.ui.form.on("ATM Leads", {
// 	refresh(frm) {

// 	},
// });

// frappe.ui.form.on('ATM Leads', {
//     validate: function(frm) {
//         // Check if the company field is selected
//         if (frm.doc.company) {
//             // Fetch permitted states from the child table of the selected company
//             frappe.call({
//                 method: "frappe.client.get_list",
//                 args: {
//                     doctype: "Permitted States", // Child Doctype name
//                     filters: {
//                         'parent': frm.doc.company // Parent field linking to the selected company
//                     },
//                     fields: ['state', 'state_code'] // Fields to retrieve for validation
//                 },
//                 async: false, // Ensure call completes before continuing
//                 callback: function(r) {
//                     if (r.message && r.message.length > 0) {
//                         // List of permitted states retrieved from the operator's child table
//                         let permitted_states = r.message;

//                         // Check if lead's state or state code matches any permitted state
//                         let is_permitted = permitted_states.some(function(d) {
//                             return (d.state === frm.doc.state) ||
//                                    (d.state_code === frm.doc.state_code);
//                         });

//                         // If no match found, block the save/submit
//                         if (!is_permitted) {
//                             frappe.validated = false; // Prevent form submission
//                             frappe.msgprint({
//                                 title: __('Not Qualified'),
//                                 message: __('This lead is not qualified for the selected operator because the state or state code is not permitted.'),
//                                 indicator: 'red'
//                             });
//                         }
//                     } else {
//                         // If no permitted states are found for the company, prevent form submission
//                         frappe.validated = false;
//                         frappe.msgprint({
//                             title: __('Validation Error'),
//                             message: __(),
//                             indicator: 'red'
//                         });
//                     }
//                 }
//             });
//         } else {
//             // If company is not selected, also prevent form submission
//             frappe.validated = false;
//             frappe.msgprint({
//                 title: __('Company Not Selected'),
//                 message: __('Please select a company before saving the lead.'),
//                 indicator: 'red'
//             });
//         }
//     }
// });
// Client script to add a button and handle lead duplication
frappe.ui.form.on('ATM Leads', {
    refresh: function(frm) {
        // Add a button to open the company selection dialog
        frm.add_custom_button(__('Duplicate for Companies'), function() {
            // Fetch all operator companies
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Operator Companies',
                    fields: ['name', 'operator_name']
                },
                callback: function(response) {
                    // Open the dialog with checkboxes for each company
                    let companies = response.message;
                    open_company_selection_dialog(frm, companies);
                }
            });
        });
    }
});

// Function to open the dialog box with company checkboxes
function open_company_selection_dialog(frm, companies) {
    let fields = companies.map(company => {
        return {
            fieldtype: 'Check',
            label: company.operator_name,
            fieldname: company.name
        };
    });

    let dialog = new frappe.ui.Dialog({
        title: __('Select Companies to Duplicate Lead'),
        fields: fields,
        primary_action_label: __('Duplicate'),
        primary_action(values) {
            // Filter selected companies
            let selected_companies = companies.filter(company => values[company.name]);

            // Duplicate lead for each selected company
            duplicate_lead_for_selected_companies(frm, selected_companies);
            dialog.hide();
        }
    });

    dialog.show();
}

// Function to duplicate the lead for the selected companies
function duplicate_lead_for_selected_companies(frm, selected_companies) {
    selected_companies.forEach(company => {
        // Duplicate the lead record for each selected company
        frappe.call({
            method: 'frappe.client.insert',
            args: {
                doc: {
                    doctype: 'ATM Leads',
                    // Copy all fields from the current lead
                    ...frm.doc,
                    name: null, // Clear the name field to create a new record
                    company: company.name, // Set the selected company
                    status: 'Draft' // Set the status to Draft for the new record
                }
            },
            callback: function(response) {
                if (response && response.message) {
                    frappe.show_alert({
                        message: __('Lead duplicated for {0}', [company.operator_name]),
                        indicator: 'green'
                    });
                }
            }
        });
    });
}

frappe.ui.form.on('ATM Leads', {
    address: function(frm) {
        // Mapping of state codes to state names
        const stateMap = {
            'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
            'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
            'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
            'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
            'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
            'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
            'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
            'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
            'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
            'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
            'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
            'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
            'WI': 'Wisconsin', 'WY': 'Wyoming'
        };

        // Function to parse address into components
        function parseAddress(address) {
            // Example input: "27252 Katy Fwy #700, Katy, TX 77494"
            let addressPattern = /(.+),\s*([^,]+),\s*([A-Z]{2})\s*(\d{5})/;
            let match = address.match(addressPattern);

            if (match) {
                let streetAddress = match[1]; // Street Address
                let city = match[2];          // City
                let stateCode = match[3];     // State Code
                let zip = match[4];           // Zip Code
                let country = "United States"; // Default to US

                // Set parsed values to the form fields
                frm.set_value('address', streetAddress);
                frm.set_value('city', city);
                frm.set_value('state_code', stateCode); // State Code
                frm.set_value('zippostal_code', zip);
                frm.set_value('country', country);

                // Set the state name based on state code if state name is not available
                let stateName = frm.doc.state || stateMap[stateCode] || "";
                frm.set_value('state', stateName);
            } else {
                frappe.msgprint(__('Address format is not recognized. Please ensure the format is "Street, City, State Zip".'));
            }
        }

        // Get the address value and parse it
        let address = frm.doc.address;
        if (address) {
            parseAddress(address);
        }
    }
});
frappe.ui.form.on('ATM Leads', {
    refresh: function(frm) {
        // Add button to copy data for Excel
        frm.add_custom_button(__('Copy For Excel'), function() {
            // Prepare the data in a tab-separated format for Excel columns
            let excelData = [
                frm.doc.company || '',
                frm.doc.post_date || '',                  // Date (Post Date)
                frm.doc.executive_name || '',             // Executive Name
                frm.doc.workflow_status || 'In Review',            // Lead Status
                frm.doc.contract_length || 'TBD',         // Contract Length
                frm.doc.fixed || 'TBD',                   // Fixed (Base Rent)
                frm.doc.per_transaction || 'TBD',         // Per Transaction
                frm.doc.owner_name || '',                 // Owner Name
                frm.doc.business_type || 'N/A',           // Business Type
                frm.doc.business_name || 'N/A',           // Business Name
                frm.doc.address || 'N/A',                 // Business Street Address
                frm.doc.city || 'N/A',                    // City
                frm.doc.state_code || 'N/A',              // State/Province
                frm.doc.zippostal_code || 'N/A',          // ZIP/Postal Code
                frm.doc.business_phone_number || 'N/A',   // Business Phone
                frm.doc.personal_cell_phone || '',        // Personal Phone
                frm.doc.email || '',                      // Email Address
                frm.doc.sign_date || '',
                frm.doc.agreement_sent_date || '',// Signed Date
                frm.doc.approve_date || ''              // Installed Date
            ];

            // Join the array with tab characters to separate into columns
            let tabSeparatedData = excelData.join('\t');

            // Create a temporary textarea element to hold the tab-separated text
            let tempTextArea = document.createElement('textarea');
            tempTextArea.value = tabSeparatedData;
            document.body.appendChild(tempTextArea);

            // Select the text inside the textarea and copy it
            tempTextArea.select();
            tempTextArea.setSelectionRange(0, 99999); // For mobile devices

            try {
                // Execute the copy command
                document.execCommand('copy');
                frappe.msgprint(__('Copied to clipboard!'));
            } catch (err) {
                frappe.msgprint(__('Failed to copy: ' + err));
            }

            // Remove the temporary textarea
            document.body.removeChild(tempTextArea);
        });
    }
});
frappe.ui.form.on('ATM Leads', {
    refresh: function(frm) {
        // Add button to copy data for Skype
        frm.add_custom_button(__('Copy for Skype'), function() {
            // Define the formatted text for Skype
            let skypeText = `
Approval Send Request:

Owner Name: ${frm.doc.owner_name || 'N/A'}

Owner Mail: mailto:${frm.doc.email || 'N/A'}

Personal Phone: ${frm.doc.personal_cell_phone || 'N/A'}

Business Name: ${frm.doc.business_name || 'N/A'}

Business Address: ${frm.doc.address || 'N/A'}, ${frm.doc.city || 'N/A'}, ${frm.doc.state || 'N/A'}, ${frm.doc.zippostal_code || 'N/A'},${frm.doc.state_code || 'N/A'}

Business Phone: ${frm.doc.business_phone_number || 'N/A'}

Operations Hours: ${frm.doc.hours || 'N/A'}

Location Type: ${frm.doc.business_type || 'N/A'}

Offer Details:

Fixed: ${frm.doc.fixed || 'TBD'}

Per Trans: ${frm.doc.per_transaction || 'TBD'}

Term: ${frm.doc.contract_length || 'TBD'} Years

Additional Notes: Please Send This Location For Approval. Thanks
`;

            // Create a temporary textarea element to hold the text
            let tempTextArea = document.createElement('textarea');
            tempTextArea.value = skypeText;
            document.body.appendChild(tempTextArea);

            // Select the text inside the textarea and copy it
            tempTextArea.select();
            tempTextArea.setSelectionRange(0, 99999); // For mobile devices

            try {
                // Execute the copy command
                document.execCommand('copy');
                frappe.msgprint(__('Copied to clipboard!'));
            } catch (err) {
                frappe.msgprint(__('Failed to copy: ' + err));
            }

            // Remove the temporary textarea
            document.body.removeChild(tempTextArea);
        });
    }
});
frappe.ui.form.on('ATM Leads', {
    refresh: function(frm) {
        // Function to check if the user has the "Data Executive" role
        function hasRole(role) {
            return frappe.user_roles.includes(role);
        }

        // Only show the buttons if the user has the "Data Executive" role
        if (hasRole('Data Executive')) {
            // Create a wrapper for grouped buttons
            frm.add_custom_button(__('Crypto Base'), function() {
                copyToClipboard([
                    frm.doc.business_name || '',
                    frm.doc.address || 'N/A',
                    frm.doc.city || 'N/A',
                    frm.doc.state_code || 'N/A',
                    frm.doc.zippostal_code || 'N/A',
                    frm.doc.hours || '',
                    frm.doc.fixed || 'TBD'
                ]);
            }, __('External')); // Add to a group labeled "Data for Excel"
            
            frm.add_custom_button(__('Un Bank'), function() {
                copyToClipboard([
                    frm.doc.post_date || '',
                    frm.doc.workflow_status || 'Pending Review',
                    frm.doc.contract_length || 'TBD',
                    frm.doc.fixed || 'TBD',
                    frm.doc.percentage || 'TBD',
                    frm.doc.business_type || '',
                    frm.doc.business_name || '',
                    frm.doc.address || 'N/A',
                    frm.doc.city || 'N/A',
                    frm.doc.state_code || 'N/A',
                    frm.doc.zippostal_code || 'N/A',
                    frm.doc.hours || ''
                ]);
            }, __('External')); // Add to the same group

            frm.add_custom_button(__('Coin Works'), function() {
                copyToClipboard([
                    frm.doc.post_date || '',
                    frm.doc.workflow_status || 'Pending Review',
                    frm.doc.contract_length || 'TBD',
                    frm.doc.fixed || 'TBD',
                    frm.doc.business_type || '',
                    frm.doc.business_name || '',
                    frm.doc.address || 'N/A',
                    frm.doc.city || 'N/A',
                    frm.doc.state_code || 'N/A',
                    frm.doc.zippostal_code || 'N/A',
                    frm.doc.hours || ''
                ]);
            }, __('External')); // Add to the same group

            frm.add_custom_button(__('Budget Coinz'), function() {
                copyToClipboard([
                    frm.doc.post_date || '',
                    frm.doc.workflow_status || 'Pending Review',
                    frm.doc.contract_length || 'TBD',
                    frm.doc.fixed || 'TBD',
                    frm.doc.percentage || 'TBD',
                    frm.doc.business_type || '',
                    frm.doc.business_name || '',
                    frm.doc.address || 'N/A',
                    frm.doc.city || 'N/A',
                    frm.doc.state_code || 'N/A',
                    frm.doc.zippostal_code || 'N/A',
                    frm.doc.hours || ''
                ]);
            }, __('External')); // Add to the same group

            frm.add_custom_button(__('Instant Coin Bank'), function() {
                copyToClipboard([
                    frm.doc.post_date || '',
                    frm.doc.workflow_status || 'Pending Review',
                    frm.doc.contract_length || 'TBD',
                    frm.doc.fixed || 'TBD',
                    frm.doc.per_transaction || 'TBD',
                    frm.doc.business_type || '',
                    frm.doc.business_name || '',
                    frm.doc.address || 'N/A',
                    frm.doc.city || 'N/A',
                    frm.doc.state_code || 'N/A',
                    frm.doc.zippostal_code || 'N/A',
                    frm.doc.hours || ''
                ]);
            }, __('External')); // Add to the same group
        }
    }
});

// Function to copy data to clipboard
function copyToClipboard(dataArray) {
    // Join the array with tab characters to separate into columns
    let tabSeparatedData = dataArray.join('\t');

    // Create a temporary textarea element to hold the tab-separated text
    let tempTextArea = document.createElement('textarea');
    tempTextArea.value = tabSeparatedData;
    document.body.appendChild(tempTextArea);

    // Select the text inside the textarea and copy it
    tempTextArea.select();
    tempTextArea.setSelectionRange(0, 99999); // For mobile devices

    try {
        // Execute the copy command
        document.execCommand('copy');
        frappe.msgprint(__('Copied to clipboard!'));
    } catch (err) {
        frappe.msgprint(__('Failed to copy: ' + err));
    }

    // Remove the temporary textarea
    document.body.removeChild(tempTextArea);
}


