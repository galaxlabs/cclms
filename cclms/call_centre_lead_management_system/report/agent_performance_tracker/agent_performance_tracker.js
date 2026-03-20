frappe.query_reports["Agent Performance Tracker"] = {
  filters: [
    {
      fieldname: "month",
      label: __("Month"),
      fieldtype: "Data",
      default: frappe.datetime.get_today().slice(0, 7),
    },
  ],
};

