frappe.query_reports["Weekly ATM KPI"] = {
    "filters": [
        {
            fieldname: "timespan",
            label: __("Time Span"),
            fieldtype: "Select",
            options: "This Week\nThis Month\nCustom",
            default: "This Week"
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        }
    ],

    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        var ratio_fields = [
            "ratio_approved_created",
            "ratio_rejected_created",
            "ratio_signed_approved",
            "ratio_converted_signed",
            "ratio_installed_signed",
            "ratio_sign_rejected_signed",
            "monthly_ratio_approved_created"
        ];

        if (ratio_fields.includes(column.fieldname)) {
            var ratio = data[column.fieldname] || 0; // %

            // Default (higher is better)
            var color = "red";
            if (ratio >= 70) {
                color = "green";
            } else if (ratio >= 40) {
                color = "orange";
            }

            // For rejection ratios, lower is better
            if (["ratio_rejected_created", "ratio_sign_rejected_signed"].includes(column.fieldname)) {
                if (ratio <= 10) {
                    color = "green";
                } else if (ratio <= 30) {
                    color = "orange";
                } else {
                    color = "red";
                }
            }

            value = `<span style="font-weight:bold; color:${color};">${value}</span>`;
        }

        // Highlight pseudo name as main label
        if (column.fieldname === "pseudo_name") {
            value = `<span style="font-weight:bold;">${value}</span>`;
        }

        return value;
    }
};

// frappe.query_reports["Weekly ATM KPI"] = {
//     "filters": [
//         {
//             "fieldname": "from_date",
//             "label": __("From Date"),
//             "fieldtype": "Date",
//             "default": frappe.datetime.get_today()
//         },
//         {
//             "fieldname": "to_date",
//             "label": __("To Date"),
//             "fieldtype": "Date",
//             "default": frappe.datetime.get_today()
//         }
//     ],

//     "formatter": function (value, row, column, data, default_formatter) {
//         value = default_formatter(value, row, column, data);
//         if (!data) return value;

//         // All ratio fields
//         var ratio_fields = [
//             "ratio_approved_created",
//             "ratio_rejected_created",
//             "ratio_signed_approved",
//             "ratio_converted_signed",
//             "ratio_installed_signed",
//             "ratio_sign_rejected_signed",
//             "monthly_ratio_approved_created"
//         ];

//         if (ratio_fields.includes(column.fieldname)) {
//             var ratio = data[column.fieldname] || 0; // %

//             // Default: higher better
//             var color = "red";
//             if (ratio >= 70) {
//                 color = "green";
//             } else if (ratio >= 40) {
//                 color = "orange";
//             }

//             // For "rejection" ratios, invert (lower is better)
//             if (["ratio_rejected_created", "ratio_sign_rejected_signed"].includes(column.fieldname)) {
//                 if (ratio <= 10) {
//                     color = "green";
//                 } else if (ratio <= 30) {
//                     color = "orange";
//                 } else {
//                     color = "red";
//                 }
//             }

//             value = `<span style="font-weight:bold; color:${color};">${value}</span>`;
//         }

//         // Highlight pseudo name (main card name)
//         if (column.fieldname === "pseudo_name") {
//             value = `<span style="font-weight:bold;">${value}</span>`;
//         }

//         return value;
//     }
// };
