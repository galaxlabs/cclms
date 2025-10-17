frappe.ready(() => {
	console.log("🌐 ATM Map Viewer loading...");

	// Step 1: Load Google Maps JS from server-side key
	frappe.call({
		method: "frappe.client.get_single",
		args: { doctype: "Google Maps Settings" },
		callback: function(r) {
			if (!r.message || !r.message.api_key) {
				console.error("No API Key found.");
				return;
			}
			const script = document.createElement('script');
			script.src = `https://maps.googleapis.com/maps/api/js?key=${r.message.api_key}&libraries=places`;
			script.async = true;
			script.defer = true;
			script.onload = initMap;
			document.head.appendChild(script);
		}
	});
});

function initMap() {
	const map = new google.maps.Map(document.getElementById("atm-map"), {
		center: { lat: 39.8283, lng: -98.5795 },
		zoom: 5,
		styles: [{ featureType: "poi", stylers: [{ visibility: "off" }] }]
	});

	// Step 2: Fetch lead data
	frappe.call({
		method: "cclms.api.map_data.get_map_data",
		callback: function(r) {
			const leads = r.message || [];
			leads.forEach(lead => {
				if (!lead.latitude || !lead.longitude) return;

				const marker = new google.maps.Circle({
					strokeColor: "#000",
					strokeOpacity: 0.5,
					strokeWeight: 1,
					fillColor: lead.color || "#888",
					fillOpacity: 0.75,
					map: map,
					center: {
						lat: parseFloat(lead.latitude),
						lng: parseFloat(lead.longitude)
					},
					radius: 100
				});

				const infoWindow = new google.maps.InfoWindow({
					content: `
						<b>${lead.company}</b><br>
						${lead.business_type || ''}<br>
						ZIP: ${lead.zippostal_code}<br>
						Zone: ${lead.zone || 'Unknown'}`
				});

				marker.addListener('click', () => {
					infoWindow.setPosition(marker.getCenter());
					infoWindow.open(map);
				});
			});
		}
	});
}
