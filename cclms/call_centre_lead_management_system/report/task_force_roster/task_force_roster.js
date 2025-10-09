frappe.query_reports["Task Force Roster"] = {
  filters: [
    { fieldname: "from_date", label: "From", fieldtype: "Date", default: frappe.datetime.month_start() },
    { fieldname: "to_date", label: "To", fieldtype: "Date", default: frappe.datetime.get_today() },
    { fieldname: "branch", label: "Branch", fieldtype: "Link", options: "Branch" },
    { fieldname: "company", label: "Operator Company", fieldtype: "Link", options: "Operator Companies" },
    {
      fieldname: "chart_type",
      label: "Chart Type",
      fieldtype: "Select",
      options: ["Bar", "Line"],
      default: "Bar"
    },
    {
      fieldname: "chart_group",
      label: "Chart Group By",
      fieldtype: "Select",
      options: ["Agent", "Date"],
      default: "Agent"
    }
  ]
};
