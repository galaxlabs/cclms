// in apps/cclms/.../page/atm_map/atm_map.js
frappe.pages['atm_map'].on_page_load = function(wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'ATM Map',
    single_column: true
  });

  page.set_primary_action('Update Competitor Density', () => {
    frappe.call({ method: 'cclms.api.ops.run_update_competitor_density',
      callback: r => frappe.msgprint(__('Done: {0}', [JSON.stringify(r.message)])) });
  })

  page.add_action_item('Update Totals', () => {
    frappe.call({ method: 'cclms.api.ops.run_update_totals',
      callback: r => frappe.msgprint(__('Done: {0}', [JSON.stringify(r.message)])) });
  })

  page.add_action_item('Apply Rules (Color/Score)', () => {
    frappe.call({ method: 'cclms.api.ops.run_apply_rules',
      callback: r => frappe.msgprint(__('Done: {0}', [JSON.stringify(r.message)])) });
  })
};

// frappe.pages['atm_map'].on_page_load = function(wrapper) {
// 	const page = frappe.ui.make_app_page({
// 		parent: wrapper,
// 		title: 'ATM Map',
// 		single_column: true
// 	});

// 	console.log("✅ ATM Map page loaded");

// 	$(page.body).html(`
// 		<div id="atm-map" style="height: 85vh; width: 100%; border: 1px solid #ccc; border-radius: 8px;"></div>
// 		<div id="atm-map-legend" style="margin-top: 10px;">
// 			<span style="color: #28a745;">● Green: Good</span> &nbsp;
// 			<span style="color: #ffc107;">● Yellow: Acceptable</span> &nbsp;
// 			<span style="color: #dc3545;">● Red: Avoid</span>
// 		</div>
// 	`);

// 	load_google_maps(() => {
// 		console.log("✅ Google Maps script loaded");
// 		init_atm_map();
// 	});
// };

// // Dynamically load Google Maps SDK using key from Google Maps Settings
// function load_google_maps(callback) {
// 	frappe.call({
// 		method: 'frappe.client.get_single',
// 		args: { doctype: 'Google Maps Settings' },
// 		callback: function(r) {
// 			if (!r.message || !r.message.api_key) {
// 				frappe.msgprint('Google Maps API key not found in Google Maps Settings.');
// 				console.error("❌ API key missing in Google Maps Settings");
// 				return;
// 			}
// 			const apiKey = r.message.api_key;
// 			console.log("🔑 Using API Key:", apiKey);

// 			const script = document.createElement('script');
// 			script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places`;
// 			script.defer = true;
// 			script.async = true;
// 			script.onload = callback;
// 			document.head.appendChild(script);
// 		}
// 	});
// }

// function init_atm_map() {
// 	console.log("📍 Initializing map...");
// 	const mapEl = document.getElementById("atm-map");
// 	if (!mapEl) {
// 		console.error("❌ #atm-map element not found in DOM");
// 		return;
// 	}

// 	const map = new google.maps.Map(mapEl, {
// 		center: { lat: 39.8283, lng: -98.5795 },
// 		zoom: 5,
// 		styles: [{ featureType: "poi", stylers: [{ visibility: "off" }] }]
// 	});

// 	// Show test marker first
// 	new google.maps.Marker({
// 		position: { lat: 40.7128, lng: -74.0060 },
// 		map: map,
// 		title: "Test Marker (NYC)"
// 	});

// 	// Now pull live ATM lead data
// 	frappe.call({
// 		method: 'cclms.api.map_data.get_map_data',
// 		callback: function(r) {
// 			const leads = r.message || [];

// 			console.log("📦 Loaded ATM leads:", leads.length);
// 			if (!leads.length) {
// 				frappe.msgprint("No ATM Leads with location found.");
// 			}

// 			leads.forEach(lead => {
// 				if (!lead.latitude || !lead.longitude) return;

// 				const marker = new google.maps.Circle({
// 					strokeColor: "#000000",
// 					strokeOpacity: 0.6,
// 					strokeWeight: 1,
// 					fillColor: lead.color || "#888",
// 					fillOpacity: 0.8,
// 					map: map,
// 					center: { lat: parseFloat(lead.latitude), lng: parseFloat(lead.longitude) },
// 					radius: 150
// 				});

// 				const info = new google.maps.InfoWindow({
// 					content: `<b>${lead.company}</b><br>${lead.business_type || ''}<br>ZIP: ${lead.zip}<br>Zone: ${lead.zone}`
// 				});

// 				marker.addListener('click', function() {
// 					info.setPosition(marker.getCenter());
// 					info.open(map);
// 				});
// 			});
// 		},
// 		error: function(e) {
// 			console.error("❌ API call to get_map_data failed", e);
// 			frappe.msgprint("Failed to load ATM leads");
// 		}
// 	});
// }
