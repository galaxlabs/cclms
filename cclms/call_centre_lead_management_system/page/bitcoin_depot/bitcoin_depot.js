frappe.pages['bitcoin-depot'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Bitcoin Depot Dashboard',
		single_column: true
	});
}