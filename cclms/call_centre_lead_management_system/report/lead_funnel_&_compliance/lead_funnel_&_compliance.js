// Copyright (c) 2025, Galaxy and contributors
// For license information, please see license.txt

/* global frappe */
frappe.query_reports["Lead Funnel & Compliance"] = {
  filters: [
    {fieldname: "from", label: "From", fieldtype: "Date", default: frappe.datetime.month_start()},
    {fieldname: "to", label: "To", fieldtype: "Date", default: frappe.datetime.get_today()},
    {fieldname: "company", label: "Operator Company", fieldtype: "Link", options: "Operator Companies"},
    {fieldname: "executive_name", label: "Executive", fieldtype: "Link", options: "Sales Agent"},
  ],
  onload: function(report) {
    // Optional: tweak chart colors (Agreement Sent bar, Signed, etc.)
    report.chart_args.colors = ["#111827", "#10b981"]; // counts, conversion%
    // NOTE: Frappe Chart colors are overall dataset colors; if you want per-bar colors,
    // we can switch this report to a Dashboard Chart or Highcharts on a custom page.
  }
};
