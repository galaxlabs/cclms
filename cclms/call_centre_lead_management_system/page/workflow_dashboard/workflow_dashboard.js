frappe.pages["workflow_dashboard"].on_page_load = function() {
  frappe.require("/assets/cclms/js/workflow_dashboard.js", () => {
    // file above executes on DOMContentLoaded
  });
};
