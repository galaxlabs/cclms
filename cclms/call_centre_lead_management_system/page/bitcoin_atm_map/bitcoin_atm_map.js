frappe.pages['bitcoin_atm_map'].on_page_load = function(wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Bitcoin ATM Map',
        single_column: true
    });

    // Add map container div and UI elements
    $(wrapper).find('.layout-main-section').append(`
        <div class="business-filter" style="margin-bottom: 15px;">
            <label for="business-type">Business Type:</label>
            <select id="business-type">
                <option value="all">All</option>
                <option value="smoke_shop">Smoke Shop</option>
                <option value="gas_station">Gas Station</option>
                <option value="convenience_store">Convenience Store</option>
            </select>

            <label for="states-checkboxes">States:</label>
            <div id="states-checkboxes" style="display: inline-block; margin-left: 10px;">
                <input type="checkbox" id="CA" value="California"> California
                <input type="checkbox" id="TX" value="Texas"> Texas
                <input type="checkbox" id="NY" value="New York"> New York
                <!-- Add more states as needed -->
            </div>

            <label for="radius">Radius (miles):</label>
            <input type="number" id="radius" min="1" max="10" value="2">
            <button id="search-businesses">Search</button>
        </div>
        <div id="map" style="height: 500px; margin-top: 20px;"></div>
    `);

    // Initialize the Leaflet map
    let map = L.map('map').setView([37.7749, -122.4194], 5); // Default view over the USA

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
    }).addTo(map);

    // Add event listener to the Search button for filtering
    $('#search-businesses').on('click', function() {
        const businessType = $('#business-type').val();
        const selectedStates = $('#states-checkboxes input:checked').map(function() {
            return $(this).val();
        }).get();
        const radius = $('#radius').val();

        // Function to handle the search and plotting will go here
        searchAndPlotBusinesses(map, businessType, selectedStates, radius);
    });
    function searchAndPlotBusinesses(map, businessType, selectedStates, radius) {
        console.log("Selected Business Type:", businessType);
        console.log("Selected States:", selectedStates);
        console.log("Radius:", radius);
    
        // Example point (e.g., New York City for testing)
        let exampleLocation = [40.7128, -74.0060];
    
        // Clear any existing markers/circles
        map.eachLayer(function(layer) {
            if (layer instanceof L.Marker || layer instanceof L.Circle) {
                map.removeLayer(layer);
            }
        });
    
        // Add an example marker and circle to the map
        L.marker(exampleLocation).addTo(map)
            .bindPopup(`<b>Example Business</b><br>Type: ${businessType}<br>State: ${selectedStates.join(', ')}`);
        L.circle(exampleLocation, { radius: radius * 1609.34 }).addTo(map); // Convert miles to meters
    }
    
};
