// Copyright (c) 2026, Galaxy and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Stage Status"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Operator Companies",
        },
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch",
        },
        {
            fieldname: "executive_name",
            label: __("Agent"),
            fieldtype: "Link",
            options: "Sales Agent",
        },
    ],
};
