// Copyright (c) 2025, Galaxy and contributors
// For license information, please see license.txt

/* global frappe */
frappe.query_reports["Workflow Transitions"] = {
  filters: [
    { fieldname: "start_date", label: "Start Date", fieldtype: "Date", default: frappe.datetime.month_start() },
    { fieldname: "end_date", label: "End Date", fieldtype: "Date", default: frappe.datetime.get_today() },
    { fieldname: "company", label: "Company", fieldtype: "Link", options: "Operator Companies" },
    { fieldname: "executive_name", label: "Executive", fieldtype: "Link", options: "Sales Agent" },
    { fieldname: "state", label: "US State / Code", fieldtype: "Data" },
    { fieldname: "exclude_drafts", label: "Exclude Drafts", fieldtype: "Check", default: 1 },
	{ fieldname: "conv_basis", label: "Conversion Basis", fieldtype: "Select",
      options: "Previous Stage\nCreated", default: "Previous Stage" },
  ],
};
