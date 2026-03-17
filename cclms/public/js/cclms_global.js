// This script runs globally for every logged-in user
frappe.provide('cclms.utils');

$(document).on('toolbar_setup', function() {
    // 1. Request Browser Notification Permission if not already set
    if (Notification.permission === "default") {
        frappe.show_alert({
            message: __("Please enable Desktop Notifications for Email & Workflow alerts."),
            indicator: "blue"
        });
        Notification.requestPermission();
    }
});

// 2. Listen for Real-time Notifications from the Backend
frappe.realtime.on('notification', function(data) {
    // Refresh the Bell Icon count
    frappe.utils.notifications.update_notifications();

    // 3. Trigger a Native Browser Popup if permission is granted
    if (Notification.permission === "granted") {
        let n = new Notification("Xperts Global Alert", {
            body: data.subject || "You have a new update in ERPNext",
            icon: '/assets/frappe/images/frappe-framework-logo.png' // Change to your logo path
        });

        n.onclick = function() {
            window.focus();
            if (data.document_type && data.document_name) {
                frappe.set_route('Form', data.document_type, data.document_name);
            }
        };
    }
});