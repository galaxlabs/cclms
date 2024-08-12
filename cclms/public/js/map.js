document.addEventListener('DOMContentLoaded', function () {
    // Initialize the map
    var map = L.map('map').setView([51.505, -0.09], 13);

    // Set up the OpenStreetMap tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap'
    }).addTo(map);

    // Initialize the marker cluster group
    var markers = L.markerClusterGroup();
    map.addLayer(markers);

    // Add search control
    var searchControl = new L.Control.GeoSearch({
        provider: new L.GeoSearch.Provider.OpenStreetMap(),
        style: 'bar',
        position: 'topleft'
    }).addTo(map);

    // Function to fetch and display business information
    function fetchAndDisplayBusinesses(type) {
        var url = `https://overpass-api.de/api/interpreter?data=[out:json];node["amenity"="${type}"](around:1000,51.505,-0.09);out;`;
        fetch(url)
            .then(response => response.json())
            .then(data => {
                // Clear existing markers
                markers.clearLayers();

                data.elements.forEach(element => {
                    var marker = L.marker([element.lat, element.lon])
                        .bindPopup(`<b>${type}</b><br>Details here.`);

                    markers.addLayer(marker);
                });
            });
    }

    // Example: Fetch and display Bitcoin ATMs
    fetchAndDisplayBusinesses('atm');

    // Add a dropdown filter for business types
    var businessTypeFilter = document.createElement('select');
    businessTypeFilter.innerHTML = `
        <option value="">Select Business Type</option>
        <option value="restaurant">Restaurant</option>
        <option value="grocery">Grocery</option>
        <option value="atm">Bitcoin ATM</option>
        <!-- Add more options as needed -->
    `;
    document.body.appendChild(businessTypeFilter);

    // Event listener for the business type filter
    businessTypeFilter.addEventListener('change', function () {
        var selectedType = this.value;
        if (selectedType) {
            fetchAndDisplayBusinesses(selectedType);
        } else {
            // Clear markers if no type is selected
            markers.clearLayers();
        }
    });

    // Function to calculate distance between two points
    function calculateDistance(lat1, lon1, lat2, lon2) {
        var R = 6371; // Radius of Earth in km
        var dLat = (lat2 - lat1) * Math.PI / 180;
        var dLon = (lon2 - lon1) * Math.PI / 180;
        var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon / 2) * Math.sin(dLon / 2);
        var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        var distance = R * c;
        return distance;
    }

    // Example: Add a marker with distance calculation
    var exampleLat = 51.505;
    var exampleLon = -0.09;
    var atmLat = 51.51;
    var atmLon = -0.1;

    var marker = L.marker([exampleLat, exampleLon]).addTo(map)
        .bindPopup(`<b>Example Location</b><br>Distance to nearest ATM: ${calculateDistance(exampleLat, exampleLon, atmLat, atmLon).toFixed(2)} km`)
        .openPopup();
});
