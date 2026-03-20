/**
 * Global Client Script for CCLMS
 * Handles Real-time Notifications and Workflow Alerts
 */

(function() {
    "use strict";

    const EVENT_NAMES = ["cclms_notification", "notification"];
    const seenNotifications = new Set();

    function requestBrowserPermission() {
        if (!window.Notification || Notification.permission !== "default") {
            return;
        }

        Notification.requestPermission().then((permission) => {
            console.log("CCLMS: Browser Notification Permission:", permission);
        });
    }

    function getRouteFromNotification(data) {
        if (Array.isArray(data.route) && data.route.length) {
            return data.route;
        }

        if (data.document_type && data.document_name) {
            return ["Form", data.document_type, data.document_name];
        }

        return null;
    }

    function showDeskAlert(data) {
        frappe.show_alert({
            message: data.subject || __("New Notification Received"),
            indicator: data.indicator || "orange"
        }, 7);
    }

    function showBrowserNotification(data) {
        if (!window.Notification || Notification.permission !== "granted") {
            return;
        }

        const dedupeKey = data.notification_id || [
            data.document_type,
            data.document_name,
            data.subject,
            data.timestamp
        ].join(":");

        if (seenNotifications.has(dedupeKey)) {
            return;
        }
        seenNotifications.add(dedupeKey);

        const notification = new Notification(data.title || "CCLMS", {
            body: data.body || data.subject || __("New Notification Received"),
            icon: data.icon || "/assets/frappe/images/frappe-framework-logo.png",
            tag: dedupeKey,
            renotify: false,
            requireInteraction: false,
        });

        notification.onclick = function(event) {
            event.preventDefault();
            window.focus();

            const route = getRouteFromNotification(data);
            if (route) {
                frappe.set_route(...route);
            }

            notification.close();
        };
    }

    function handleRealtimeNotification(data) {
        if (!data) {
            return;
        }

        console.log("CCLMS: Real-time Event Received!", data);
        showDeskAlert(data);

        if (document.hidden || !document.hasFocus()) {
            showBrowserNotification(data);
            return;
        }

        // Still show a browser notification for foreground users when explicitly allowed by the payload.
        if (data.force_browser_notification) {
            showBrowserNotification(data);
        }
    }

    // Wait for the app to be fully ready
    $(document).on('app_ready', function() {
        console.log("CCLMS: Global Script Loaded and App Ready");

        // 1. Request Browser Notification Permissions on first load
        requestBrowserPermission();

        // Ask again after the first user interaction if the initial load did not grant it.
        document.addEventListener("click", requestBrowserPermission, { once: true });

        // 2. Listen for server-pushed notification events.
        EVENT_NAMES.forEach((eventName) => {
            frappe.realtime.on(eventName, handleRealtimeNotification);
        });

        // 3. Optional: Heartbeat check to confirm listener is active
        console.log("CCLMS: Real-time listeners are now active.", EVENT_NAMES);
    });
})();
