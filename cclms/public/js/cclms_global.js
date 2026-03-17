// cclms_global.js - v15 Compatible
$(document).on('app_ready', function() {
    // 1. Setup Browser Notification Permissions
    if (window.Notification && Notification.permission === "default") {
        Notification.requestPermission();
    }

    // 2. Listen for Real-time Notifications
    // The 'msgprint' and 'eval_js' are standard, but we use 'notification' 
    // because that's what we named the event in our Python code.
    frappe.realtime.on('notification', function(data) {
        // Show the orange/blue toast in the top right
        frappe.show_alert({
            message: data.subject || __("New Update Received"),
            indicator: data.indicator || "orange"
        }, 7);

        // Trigger the native System/Chrome notification
        if (window.Notification && Notification.permission === "granted") {
            let n = new Notification("Xperts Global", {
                body: data.subject,
                icon: '/assets/frappe/images/frappe-framework-logo.png'
            });
            n.onclick = function() {
                window.focus();
                if (data.document_type && data.document_name) {
                    frappe.set_route('Form', data.document_type, data.document_name);
                }
            };
        }
    });
});