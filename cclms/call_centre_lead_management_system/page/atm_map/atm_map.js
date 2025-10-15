frappe.pages['atm-map'].on_page_load = function(wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'ATM Scouting Map',
		single_column: true
	});
  
	$(frappe.render_template('atm_map_html')).appendTo(page.body);
	init_atm_map();
  };
  
  function init_atm_map() {
	const map = L.map('atm-map-view').setView([37.8, -96], 4);
	L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
		maxZoom: 18,
		attribution: '&copy; OpenStreetMap contributors'
	}).addTo(map);
  
	// Fetch our lead data
	frappe.call({
		method: 'cclms.api.map_data.get_atm_map_data',
		callback: function(r) {
			const data = r.message;
			L.geoJSON(data, {
				pointToLayer: function (feature, latlng) {
					return L.circleMarker(latlng, {
						radius: 6,
						fillColor: feature.properties.color,
						color: '#000',
						weight: 1,
						opacity: 1,
						fillOpacity: 0.8
					});
				},
				onEachFeature: function (feature, layer) {
					layer.bindPopup(
						`<b>${feature.properties.business || 'N/A'}</b><br>
						 ${feature.properties.type || ''}<br>
						 Zone: <b style="color:${feature.properties.color}">${feature.properties.zone}</b><br>
						 Status: ${feature.properties.status}<br>
						 <i>ZIP: ${feature.properties.zip}</i>`
					);
				}
			}).addTo(map);
		}
	});
  }
  