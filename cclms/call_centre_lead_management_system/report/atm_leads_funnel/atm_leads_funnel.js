/* global frappe */
/* global frappe */

frappe.query_reports["ATM Leads Funnel"] = {
  filters: [
    {
      fieldname: "time_span",
      label: "Time Span",
      fieldtype: "Select",
      options: [
        "Custom Range",
        "This Week",
        "Last Week",
        "This Month",
        "Last Month"
      ],
      default: "This Month",
      reqd: 1,
      on_change: function () {
        const span = frappe.query_report.get_filter_value("time_span");
        let from, to;
        const today = frappe.datetime.get_today();

        switch (span) {
          case "This Week":
            from = frappe.datetime.week_start();
            to = frappe.datetime.week_end();
            break;
          case "Last Week":
            from = frappe.datetime.add_days(frappe.datetime.week_start(), -7);
            to = frappe.datetime.add_days(frappe.datetime.week_end(), -7);
            break;
          case "This Month":
            from = frappe.datetime.month_start();
            to = frappe.datetime.month_end();
            break;
          case "Last Month":
            from = frappe.datetime.add_months(frappe.datetime.month_start(), -1);
            to = frappe.datetime.add_months(frappe.datetime.month_end(), -1);
            break;
          default:
            return; // Custom Range: don't override manual selection
        }

        frappe.query_report.set_filter_value("from_date", from);
        frappe.query_report.set_filter_value("to_date", to);

        // ✅ Force backend refresh (ignore prepared/cached data)
        frappe.query_report.refresh(true);
      }
    },
    {
      fieldname: "from_date",
      label: "From Date",
      fieldtype: "Date",
      default: frappe.datetime.month_start(),
      reqd: 1,
      on_change: function () {
        if (frappe.query_report.get_filter_value("time_span") === "Custom Range") {
          frappe.query_report.refresh(true);
        }
      }
    },
    {
      fieldname: "to_date",
      label: "To Date",
      fieldtype: "Date",
      default: frappe.datetime.month_end(),
      reqd: 1,
      on_change: function () {
        if (frappe.query_report.get_filter_value("time_span") === "Custom Range") {
          frappe.query_report.refresh(true);
        }
      }
    },
    {
      fieldname: "branch",
      label: "Branch",
      fieldtype: "Link",
      options: "Branch"
    },
    {
      fieldname: "company",
      label: "Operator Company",
      fieldtype: "Link",
      options: "Operator Companies"
    },
    {
      fieldname: "executive_name",
      label: "Sales Agent",
      fieldtype: "Link",
      options: "Sales Agent"
    }
  ],

  onload: function (report) {
    // Reset toolbar first
    report.page.clear_inner_toolbar();

    // Excel Export
    report.page.add_inner_button(__("Export Excel"), function () {
      frappe.query_report.export_report("Excel");
    });

    // CSV Export
    report.page.add_inner_button(__("Export CSV"), function () {
      frappe.query_report.export_report("CSV");
    });
  }
};

// frappe.query_reports["ATM Leads Funnel"] = {
//   filters: [
//     {
//       fieldname: "time_span",
//       label: "Time Span",
//       fieldtype: "Select",
//       options: [
//         "Custom Range",
//         "This Week",
//         "Last Week",
//         "This Month",
//         "Last Month"
//       ],
//       default: "This Month",
//       reqd: 1,
//       on_change: function () {
//         const span = frappe.query_report.get_filter_value("time_span");
//         let from, to;
//         const today = frappe.datetime.get_today();

//         // 🔹 Calculate dates dynamically
//         switch (span) {
//           case "This Week":
//             from = frappe.datetime.week_start();
//             to = frappe.datetime.week_end();
//             break;
//           case "Last Week":
//             from = frappe.datetime.add_days(frappe.datetime.week_start(), -7);
//             to = frappe.datetime.add_days(frappe.datetime.week_end(), -7);
//             break;
//           case "This Month":
//             from = frappe.datetime.month_start();
//             to = frappe.datetime.month_end();
//             break;
//           case "Last Month":
//             from = frappe.datetime.add_months(frappe.datetime.month_start(), -1);
//             to = frappe.datetime.add_months(frappe.datetime.month_end(), -1);
//             break;
//           default:
//             // Custom Range — don’t override user’s manual selection
//             return;
//         }

//         frappe.query_report.set_filter_value("from_date", from);
//         frappe.query_report.set_filter_value("to_date", to);

//         // ✅ Force full data refresh
//         frappe.query_report.refresh();
//       }
//     },
//     {
//       fieldname: "from_date",
//       label: "From Date",
//       fieldtype: "Date",
//       default: frappe.datetime.month_start(),
//       reqd: 1,
//       on_change: function () {
//         if (frappe.query_report.get_filter_value("time_span") === "Custom Range") {
//           frappe.query_report.refresh();
//         }
//       }
//     },
//     {
//       fieldname: "to_date",
//       label: "To Date",
//       fieldtype: "Date",
//       default: frappe.datetime.month_end(),
//       reqd: 1,
//       on_change: function () {
//         if (frappe.query_report.get_filter_value("time_span") === "Custom Range") {
//           frappe.query_report.refresh();
//         }
//       }
//     },
//     {
//       fieldname: "branch",
//       label: "Branch",
//       fieldtype: "Link",
//       options: "Branch"
//     },
//     {
//       fieldname: "company",
//       label: "Operator Company",
//       fieldtype: "Link",
//       options: "Operator Companies"
//     },
//     {
//       fieldname: "executive_name",
//       label: "Sales Agent",
//       fieldtype: "Link",
//       options: "Sales Agent"
//     },
//   ],

//   onload: function (report) {
//     // ✅ Reset toolbar to prevent duplicate buttons
//     report.page.clear_inner_toolbar();

//     // 🧭 Export buttons
//     report.page.add_inner_button(__("Export Excel"), function () {
//       frappe.query_report.export_report("Excel");
//     });

//     report.page.add_inner_button(__("Export CSV"), function () {
//       frappe.query_report.export_report("CSV");
//     });

//     // ✅ Highlight active time span filter (optional Tailwind-friendly style)
//     const timeSpanField = report.get_filter("time_span");
//     timeSpanField.df.reqd = 1;
//   }
// };

// /* global frappe */

// frappe.query_reports["ATM Leads Funnel"] = {
//   filters: [
//     {
//       fieldname: "time_span",
//       label: "Time Span",
//       fieldtype: "Select",
//       options: [
//         "Custom Range",
//         "This Week",
//         "Last Week",
//         "This Month",
//         "Last Month"
//       ],
//       default: "This Month",
//       reqd: 1,
//       on_change: function () {
//         const span = frappe.query_report.get_filter_value("time_span");
//         let from, to;
//         const today = frappe.datetime.get_today();

//         // 🔹 Calculate dates dynamically
//         switch (span) {
//           case "This Week":
//             from = frappe.datetime.week_start();
//             to = frappe.datetime.week_end();
//             break;
//           case "Last Week":
//             from = frappe.datetime.add_days(frappe.datetime.week_start(), -7);
//             to = frappe.datetime.add_days(frappe.datetime.week_end(), -7);
//             break;
//           case "This Month":
//             from = frappe.datetime.month_start();
//             to = frappe.datetime.month_end();
//             break;
//           case "Last Month":
//             from = frappe.datetime.add_months(frappe.datetime.month_start(), -1);
//             to = frappe.datetime.add_months(frappe.datetime.month_end(), -1);
//             break;
//           default:
//             // Custom Range — don’t override user’s manual selection
//             return;
//         }

//         frappe.query_report.set_filter_value("from_date", from);
//         frappe.query_report.set_filter_value("to_date", to);

//         // ✅ Force full data refresh
//         frappe.query_report.refresh();
//       }
//     },
//     {
//       fieldname: "from_date",
//       label: "From Date",
//       fieldtype: "Date",
//       default: frappe.datetime.month_start(),
//       reqd: 1,
//       on_change: function () {
//         if (frappe.query_report.get_filter_value("time_span") === "Custom Range") {
//           frappe.query_report.refresh();
//         }
//       }
//     },
//     {
//       fieldname: "to_date",
//       label: "To Date",
//       fieldtype: "Date",
//       default: frappe.datetime.month_end(),
//       reqd: 1,
//       on_change: function () {
//         if (frappe.query_report.get_filter_value("time_span") === "Custom Range") {
//           frappe.query_report.refresh();
//         }
//       }
//     },
//     {
//       fieldname: "branch",
//       label: "Branch",
//       fieldtype: "Link",
//       options: "Branch"
//     },
//     {
//       fieldname: "company",
//       label: "Operator Company",
//       fieldtype: "Link",
//       options: "Operator Companies"
//     },
//     {
//       fieldname: "executive_name",
//       label: "Sales Agent",
//       fieldtype: "Link",
//       options: "Sales Agent"
//     }
//   ],

//   onload: function (report) {
//     // ✅ Reset toolbar to prevent duplicate buttons
//     report.page.clear_inner_toolbar();

//     // 🧭 Export buttons
//     report.page.add_inner_button(__("Export Excel"), function () {
//       frappe.query_report.export_report("Excel");
//     });

//     report.page.add_inner_button(__("Export CSV"), function () {
//       frappe.query_report.export_report("CSV");
//     });

//     // ✅ Highlight active time span filter (optional Tailwind-friendly style)
//     const timeSpanField = report.get_filter("time_span");
//     timeSpanField.df.reqd = 1;
//   }
// };
