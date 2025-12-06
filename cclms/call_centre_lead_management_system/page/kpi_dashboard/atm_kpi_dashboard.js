frappe.pages['tm-kpi-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'TM KPI Dashboard',
		single_column: true
	});
}