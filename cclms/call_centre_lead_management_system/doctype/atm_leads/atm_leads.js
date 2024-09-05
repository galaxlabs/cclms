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


