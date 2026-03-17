/**
 * Global Client Script for CCLMS
 * Handles Real-time Notifications and Workflow Alerts
 */

(function() {
    "use strict";

    // Wait for the app to be fully ready
    $(document).on('app_ready', function() {
        console.log("CCLMS: Global Script Loaded and App Ready");

        // 1. Request Browser Notification Permissions on first load
        if (window.Notification && Notification.permission === "default") {
            Notification.requestPermission().then(permission => {
                console.log("CCLMS: Browser Notification Permission:", permission);
            });
        }

        // 2. Listen for 'notification' events from Python (frappe.publish_realtime)
        frappe.realtime.on('notification', function(data) {
            console.log("CCLMS: Real-time Event Received!", data);

            // A. Show the Frappe Toast (The sliding bar in top-right)
            frappe.show_alert({
                message: data.subject || __("New Notification Received"),
                indicator: data.indicator || "orange"
            }, 7);

            // B. Show Browser Native Notification (Even if the tab is in the background)
            if (window.Notification && Notification.permission === "granted") {
                const options = {
                    body: data.subject,
                    icon: '/assets/frappe/images/frappe-framework-logo.png', // Or your custom logo
                    sticky: false
                };

                const n = new Notification("Xperts Global ATM", options);

                n.onclick = function(event) {
                    event.preventDefault();
                    window.focus();
                    
                    // If the notification includes a document link, take the user there
                    if (data.document_type && data.document_name) {
                        frappe.set_route('Form', data.document_type, data.document_name);
                    }
                };
            }
        });

        // 3. Optional: Heartbeat check to confirm listener is active
        console.log("CCLMS: Real-time Listener 'notification' is now active.");
    });
})();