// Copyright (c) 2025, Galaxy and contributors
// For license information, please see license.txt

/* global frappe */

frappe.query_reports["Executive Performance"] = {
  filters: [
    {
      fieldname: "from_date",
      label: "From",
      fieldtype: "Date",
      default: frappe.datetime.add_months(frappe.datetime.month_start(), -2)
    },
    {
      fieldname: "to_date",
      label: "To",
      fieldtype: "Date",
      default: frappe.datetime.get_today()
    },
    {
      fieldname: "company",
      label: "Operator Company",
      fieldtype: "Link",
      options: "Operator Companies"
    },
    {
      fieldname: "branch",
      label: "Branch",
      fieldtype: "Select",
      options: ["", "Karachi", "Lahore"],
      default: ""
    }
  ],
  onload: function (report) {
    report.page.set_inner_btn_group_as_primary(__("Export"));
  }
};
