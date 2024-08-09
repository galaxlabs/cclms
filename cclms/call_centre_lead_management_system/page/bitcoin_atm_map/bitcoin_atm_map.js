frappe.pages['bitcoin-atm-map'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Bitcoin ATM Map',
        single_column: true
    });

    // Add search input and map div
    $(wrapper).find('.layout-main-section').append(`
        <div style="display: flex; justify-content: center; margin-bottom: 10px;">
            <input type="text" id="location-search" 
                placeholder="Search location..." 
                style="width: 300px; padding: 5px; border-radius: 4px; border: 1px solid #ccc;">
        </div>
        <div id="map" style="height: 600px; width: 100%; border-radius: 4px;"></div>
    `);

    // Initialize the map
    var map = L.map('map').setView([51.505, -0.09], 13);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap'
    }).addTo(map);

    // Add a marker for an example Bitcoin ATM
    L.marker([51.505, -0.09]).addTo(map)
        .bindPopup('Example Bitcoin ATM Location')
        .openPopup();

    // Add event listener for the search input
    document.getElementById('location-search').addEventListener('keypress', function(e) {
        if(e.key === 'Enter') {
            var query = e.target.value;
            searchLocation(query, map);
        }
    });
}

// Function to search for a location
function searchLocation(query, map) {
    frappe.call({
        method: 'cclms.api.search_location',
        args: {
            query: query
        },
        callback: function(r) {
            if(r.message && r.message.length > 0) {
                var result = r.message[0];
                var lat = parseFloat(result.lat);
                var lon = parseFloat(result.lon);

                // Update map position
                map.setView([lat, lon], 13);

                // Add a marker
                L.marker([lat, lon]).addTo(map)
                    .bindPopup(result.display_name)
                    .openPopup();
            } else {
                frappe.msgprint('Location not found!');
            }
        }
    });
}

//##########################
// frappe.pages['bitcoin-atm-map'].on_page_load = function(wrapper) {
//     var page = frappe.ui.make_app_page({
//         parent: wrapper,
//         title: 'Bitcoin ATM Map',
//         single_column: true
//     });

//     // Add search input and map div
//     $(wrapper).find('.layout-main-section').append(`
//         <div style="display: flex; justify-content: center; margin-bottom: 10px;">
//             <input type="text" id="location-search" 
//                 placeholder="Search location..." 
//                 style="width: 300px; padding: 5px; border-radius: 4px; border: 1px solid #ccc;">
//         </div>
//         <div id="map" style="height: 600px; width: 100%; border-radius: 4px;"></div>
//     `);

//     // Initialize the map
//     var map = L.map('map').setView([51.505, -0.09], 13);

//     // Add OpenStreetMap tiles
//     L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
//         maxZoom: 19,
//         attribution: '© OpenStreetMap'
//     }).addTo(map);

//     // Add a marker for an example Bitcoin ATM
//     L.marker([51.505, -0.09]).addTo(map)
//         .bindPopup('Example Bitcoin ATM Location')
//         .openPopup();

//     // Add event listener for the search input
//     document.getElementById('location-search').addEventListener('keypress', function(e) {
//         if(e.key === 'Enter') {
//             var query = e.target.value;
//             searchLocation(query, map);
//         }
//     });
// }

// // Function to search for a location
// function searchLocation(query, map) {
//     var url = `https://nominatim.openstreetmap.org/search?format=json&q=${query}`;

//     frappe.xhr({
//         method: 'GET',
//         args: {
//             url: url
//         },
//         callback: function(r) {
//             if(r.message && r.message.length > 0) {
//                 var result = r.message[0];
//                 var lat = parseFloat(result.lat);
//                 var lon = parseFloat(result.lon);
    
//                 // Update map position
//                 map.setView([lat, lon], 13);
    
//                 // Add a marker
//                 L.marker([lat, lon]).addTo(map)
//                     .bindPopup(result.display_name)
//                     .openPopup();
//             } else {
//                 frappe.msgprint('Location not found!');
//             }
//         }
//     });
// }
// ###############
// frappe.pages['bitcoin-atm-map'].on_page_load = function(wrapper) {
// 	var page = frappe.ui.make_app_page({
// 		parent: wrapper,
// 		title: 'Bitcoin Atm Map',
// 		single_column: true
// 	});
//     // Add search input and map div
//     $(wrapper).find('.layout-main-section').append(`
//         <input type="text" id="location-search" placeholder="Search location..." style="margin-bottom: 10px; width: 300px;">
//         <div id="map" style="height: 600px;"></div>
//     `);

//     // Initialize the map (Leaflet is already loaded)
//     var map = L.map('map').setView([51.505, -0.09], 13);

//     // Add OpenStreetMap tiles
//     L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
//         maxZoom: 19,
//         attribution: '© OpenStreetMap'
//     }).addTo(map);

//     // Add a marker for an example Bitcoin ATM
//     L.marker([51.505, -0.09]).addTo(map)
//         .bindPopup('Example Bitcoin ATM Location')
//         .openPopup();

//     // Add event listener for the search input
//     document.getElementById('location-search').addEventListener('keypress', function(e) {
//         if(e.key === 'Enter') {
//             var query = e.target.value;
//             searchLocation(query, map);
//         }
//     });
// }

// // Function to search for a location
// function searchLocation(query, map) {
//     var url = `https://nominatim.openstreetmap.org/search?format=json&q=${query}`;

//     frappe.call({
//         method: 'frappe.client.get',
//         args: {
//             url: url
//         },
//         callback: function(r) {
//             if(r.message && r.message.length > 0) {
//                 var result = r.message[0];
//                 var lat = parseFloat(result.lat);
//                 var lon = parseFloat(result.lon);

//                 // Update map position
//                 map.setView([lat, lon], 13);

//                 // Add a marker
//                 L.marker([lat, lon]).addTo(map)
//                     .bindPopup(result.display_name)
//                     .openPopup();
//             } else {
//                 frappe.msgprint('Location not found!');
//             }
//         }
//     });
// }
