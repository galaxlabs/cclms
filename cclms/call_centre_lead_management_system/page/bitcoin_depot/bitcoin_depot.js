frappe.pages['bitcoin-depot'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Bitcoin Depot Dashboard',
		single_column: true
	});

	page.add_inner_button(__('Refresh Bitcoin Depot Data'), function() {
		frappe.call({
			method: 'cclms.api.ops.run_update_competitor_density',
			callback: function(r) {
				frappe.msgprint(__('Bitcoin Depot data refresh initiated. {0}', [r.message]));
			}
		});
			page.add_inner_button(__('Refresh Bitcoin Depot Data'), function() {
		frappe.call({
			method: 'cclms.api.ops.run_update_totals',
			callback: function(r) {
				frappe.msgprint(__('Bitcoin Depot data refresh initiated. {0}', [r.message]));
			}
		});
	});
	
	});
}