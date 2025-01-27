frappe.pages['telegram-chat-view'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Telegram Chat',
		single_column: true
	});
}