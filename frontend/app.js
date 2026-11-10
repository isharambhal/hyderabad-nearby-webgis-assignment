
/* ==========================================================
   HYDERABAD NEARBY SERVICES WEBGIS
   Existing functionality + UI improvements
   ========================================================== */

// ----------------------------------------------------------
// 1. MAP INITIALIZATION
// ----------------------------------------------------------

const map = L.map('map').setView([17.385, 78.4867], 11);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);


// ----------------------------------------------------------
// 2. MAP MARKER STYLES
// ----------------------------------------------------------

const myLocationIcon = L.divIcon({
    className: 'my-location-marker',
    html: `
        <div style="
            width: 25px;
            height: 25px;
            box-sizing: border-box;
            border: 3px solid white;
            border-radius: 50%;
            background: #cb756b;
            box-shadow: 0 0 0 5px rgba(203,117,107,.20),
                        0 2px 8px rgba(0,0,0,.30);
            display: flex;
            align-items: center;
            justify-content: center;
        ">
            <div style="
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: white;
            "></div>
        </div>
    `,
    iconSize: [25, 25],
    iconAnchor: [12, 12]
});

const serviceIcon = L.divIcon({
    className: 'service-map-marker',
    html: `
        <div style="
            width: 15px;
            height: 15px;
            box-sizing: border-box;
            border: 2px solid white;
            border-radius: 50%;
            background: #537e76;
            box-shadow: 0 1px 5px rgba(0,0,0,.30);
        "></div>
    `,
    iconSize: [15, 15],
    iconAnchor: [7, 7]
});

const selectedServiceIcon = L.divIcon({
    className: 'selected-service-marker',
    html: `
        <div style="
            width: 19px;
            height: 19px;
            box-sizing: border-box;
            border: 3px solid white;
            border-radius: 50%;
            background: #d69b49;
            box-shadow: 0 0 0 3px rgba(214,155,73,.28),
                        0 2px 6px rgba(0,0,0,.25);
        "></div>
    `,
    iconSize: [19, 19],
    iconAnchor: [9, 9]
});


// ----------------------------------------------------------
// 3. MAP LAYERS AND APPLICATION STATE
// ----------------------------------------------------------

let wardLayer;
let selectedLocation;
let originMarker;
let radiusCircle;

const resultLayer = L.layerGroup().addTo(map);
const markersById = new Map();

let activeId = null;
let allSubcategories = [];

const geoserverUrl =
    'http://localhost:8080/geoserver/hyderabad/wms';

const geoserverWards = L.tileLayer.wms(geoserverUrl, {
    layers: 'hyderabad:wards',
    format: 'image/png',
    transparent: true,
    version: '1.1.1',
    attribution: 'Ward boundaries: GeoServer'
});

const geoserverServices = L.tileLayer.wms(geoserverUrl, {
    layers: 'hyderabad:services',
    format: 'image/png',
    transparent: true,
    version: '1.1.1',
    attribution: 'Service points: GeoServer'
});


// ----------------------------------------------------------
// 4. HELPERS
// ----------------------------------------------------------

const $ = id => document.getElementById(id);

const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
}[char]));

function message(text, type = '') {
    const el = $('message');
    el.textContent = text;
    el.className = 'message' + (type ? ' ' + type : '');
}

function setStatus(text, ok = true) {
    const el = $('api-status');

    el.textContent = text;
    el.style.borderColor = ok ? '#b7d6c3' : '#f2b9b4';
    el.style.color = ok ? '#416c64' : '#a83d35';
}

function setGeoServerStatus(text, ok = true) {
    const el = $('geoserver-status');

    if (!el) return;

    el.textContent = text;
    el.className = 'message ' + (ok ? 'success' : 'error');
}

function validCoords(lat, lon) {
    return Number.isFinite(lat) &&
        Number.isFinite(lon) &&
        lat >= -90 &&
        lat <= 90 &&
        lon >= -180 &&
        lon <= 180;
}

function formatDistance(metres) {
    const distance = Number(metres);

    if (!Number.isFinite(distance)) return 'Distance unavailable';

    return distance < 1000
        ? `${Math.round(distance)} m`
        : `${(distance / 1000).toFixed(2)} km`;
}


// ----------------------------------------------------------
// 5. SELECTED-LOCATION SUMMARY
// ----------------------------------------------------------

function updateLocationSummary(lat, lon) {
    const summary = $('location-summary-text');

    if (!summary) return;

    if (lat == null || lon == null) {
        summary.textContent =
            'Choose a point on the map or enter coordinates.';
        return;
    }

    summary.textContent =
        `Lat ${Number(lat).toFixed(5)} · Lon ${Number(lon).toFixed(5)}`;
}


// ----------------------------------------------------------
// 6. SET THE SELECTED LOCATION
// ----------------------------------------------------------

function setLocation(lat, lon, zoom = true) {
    if (!validCoords(lat, lon)) {
        message('Please enter valid latitude and longitude values.', 'error');
        return false;
    }

    selectedLocation = { lat, lon };

    $('lat').value = lat.toFixed(6);
    $('lon').value = lon.toFixed(6);

    updateLocationSummary(lat, lon);

    if (originMarker) {
        map.removeLayer(originMarker);
    }

    originMarker = L.marker([lat, lon], {
        icon: myLocationIcon,
        title: 'Your selected location',
        zIndexOffset: 1000
    }).addTo(map);

    originMarker.bindPopup(`
        <div>
            <strong>Your selected location</strong>
            <p style="margin:5px 0 0">
                ${lat.toFixed(5)}, ${lon.toFixed(5)}
            </p>
        </div>
    `);

    if (zoom) {
        map.setView([lat, lon], 14);
    }

    if (radiusCircle) {
        map.removeLayer(radiusCircle);
        radiusCircle = null;
    }

    return true;
}


// ----------------------------------------------------------
// 7. CLICK THE MAP TO SELECT A LOCATION
// ----------------------------------------------------------

map.on('click', event => {
    if (setLocation(event.latlng.lat, event.latlng.lng, false)) {
        message(
            'Map location selected. Choose your filters and search.',
            'success'
        );
    }
});


// ----------------------------------------------------------
// 8. API REQUEST HELPER
// ----------------------------------------------------------

async function getJson(url) {
    const response = await fetch(url);

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error('Server returned an unreadable response.');
    }

    if (!response.ok) {
        throw new Error(
            data.error ||
            data.message ||
            `Request failed (${response.status})`
        );
    }

    return data;
}


// ----------------------------------------------------------
// 9. GEOSERVER LAYER CONTROLS
// ----------------------------------------------------------

function setupGeoServerControls() {
    const wardsToggle = $('toggle-wards');
    const servicesToggle = $('toggle-services');

    if (!wardsToggle || !servicesToggle) {
        setGeoServerStatus(
            'GeoServer controls are missing from index.html.',
            false
        );
        return;
    }

    // Add the ward overlay only when enabled.
    if (wardsToggle.checked) {
        geoserverWards.addTo(map);
    }

    wardsToggle.addEventListener('change', () => {
        if (wardsToggle.checked) {
            geoserverWards.addTo(map);
        } else {
            map.removeLayer(geoserverWards);
        }
    });

    servicesToggle.addEventListener('change', () => {
        if (servicesToggle.checked) {
            geoserverServices.addTo(map);
        } else {
            map.removeLayer(geoserverServices);
        }
    });

    // Check the WMS endpoint.
    // This direct request may still fail if GeoServer CORS
    // is not configured. The WMS proxy is a separate change.
    fetch(
        geoserverUrl +
        '?service=WMS&version=1.1.1&request=GetCapabilities'
    )
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return response.text();
        })
        .then(xml => {
            if (
                !xml.includes('WMS_Capabilities') &&
                !xml.includes('WMT_MS_Capabilities')
            ) {
                throw new Error('Unexpected WMS response');
            }

            setGeoServerStatus(
                'GeoServer WMS connected. Toggle layers above.',
                true
            );
        })
        .catch(error => {
            console.error('GeoServer WMS check failed:', error);

            setGeoServerStatus(
                'WMS check failed. Check GeoServer and its CORS settings.',
                false
            );
        });
}


// ----------------------------------------------------------
// 10. INITIALIZE THE APPLICATION
// ----------------------------------------------------------

async function init() {
    setupGeoServerControls();

    updateLocationSummary(null, null);

    try {
        const health = await getJson('/api/health');

        setStatus(`API connected · ${health.wards} wards`, true);

        // Load ward GeoJSON as a fallback layer.
        const geo = await getJson('/api/wards');

        wardLayer = L.geoJSON(geo, {
            style: () => ({
                color: '#829bb5',
                weight: 1,
                fillColor: '#b9cfc2',
                fillOpacity: 0.10
            }),

            onEachFeature: (feature, layer) => {
                layer.bindTooltip(
                    esc(feature.properties?.Name || 'Ward')
                );
            }
        });

        // Keep the GeoJSON layer available as a fallback,
        // but do not add it automatically to avoid duplicates
        // when the GeoServer ward layer is displayed.

        if (wardLayer.getBounds().isValid()) {
            map.fitBounds(
                wardLayer.getBounds(),
                { padding: [12, 12] }
            );
        }

        // Load service categories.
        const cats = await getJson('/api/categories');

        allSubcategories = cats.subcategories || [];

        const categorySelect = $('category');

        (cats.categories || []).forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            categorySelect.appendChild(option);
        });

        refreshSubcategories();

        message(
            `Ready. ${health.services} database service records are available. Nearby search uses the backend.`,
            'success'
        );

    } catch (error) {
        console.error('Application initialization failed:', error);

        setStatus('API/database unavailable', false);

        message(
            `${error.message} Check PostgreSQL/PostGIS, .env, and the Flask backend.`,
            'error'
        );
    }
}


// ----------------------------------------------------------
// 11. CATEGORY AND SUBCATEGORY FILTERS
// ----------------------------------------------------------

function refreshSubcategories() {
    const category = $('category').value;
    const select = $('subcategory');

    select.innerHTML =
        '<option value="">All subcategories</option>';

    allSubcategories
        .filter(item => !category || item.category === category)
        .forEach(item => {
            const option = document.createElement('option');
            option.value = item.subcategory;
            option.textContent = item.subcategory;
            select.appendChild(option);
        });
}

$('category').addEventListener('change', refreshSubcategories);


// ----------------------------------------------------------
// 12. APPLY MANUALLY ENTERED COORDINATES
// ----------------------------------------------------------

$('apply-coords').addEventListener('click', () => {
    if (
        setLocation(
            Number($('lat').value),
            Number($('lon').value)
        )
    ) {
        message(
            'Coordinates selected. Run a search when ready.',
            'success'
        );
    }
});


// ----------------------------------------------------------
// 13. USE THE BROWSER'S CURRENT LOCATION
// ----------------------------------------------------------

$('use-location').addEventListener('click', () => {
    if (!navigator.geolocation) {
        message(
            'Geolocation is unavailable. Enter coordinates or click the map.',
            'error'
        );
        return;
    }

    message('Requesting your location…');

    navigator.geolocation.getCurrentPosition(
        position => {
            const success = setLocation(
                position.coords.latitude,
                position.coords.longitude
            );

            if (success) {
                message('Your current location is selected.', 'success');
            }
        },

        error => {
            const text = error.code === 1
                ? 'Location permission denied. Allow browser location access or select a map location.'
                : error.code === 2
                    ? 'Your location could not be determined. Try again or select a map location.'
                    : 'Location request timed out. Try again or select a map location.';

            message(text, 'error');
        },

        {
            enableHighAccuracy: true,
            timeout: 12000,
            maximumAge: 60000
        }
    );
});


// ----------------------------------------------------------
// 14. CLEAR OLD SEARCH RESULTS
// ----------------------------------------------------------

function clearResults() {
    resultLayer.clearLayers();
    markersById.clear();

    $('results').innerHTML = '';
    $('result-count').textContent = '0';

    activeId = null;
}


// ----------------------------------------------------------
// 15. SELECT A RESULT CARD OR MARKER
// ----------------------------------------------------------

function selectResult(id) {
    activeId = String(id);

    document.querySelectorAll('.result-card').forEach(card => {
        card.classList.toggle(
            'active',
            card.dataset.id === activeId
        );
    });

    // Redraw markers so the selected result stands out.
    markersById.forEach((marker, markerId) => {
        marker.setIcon(
            markerId === activeId
                ? selectedServiceIcon
                : serviceIcon
        );
    });

    const marker = markersById.get(activeId);

    if (marker) {
        map.panTo(marker.getLatLng());
        marker.openPopup();
    }
}


// ----------------------------------------------------------
// 16. RENDER SEARCH RESULTS
// ----------------------------------------------------------

function renderResults(data) {
    clearResults();

    const results = Array.isArray(data.results)
        ? data.results
        : [];

    $('result-count').textContent = String(results.length);

    if (radiusCircle) {
        map.removeLayer(radiusCircle);
        radiusCircle = null;
    }

    if (
        selectedLocation &&
        $('mode').value !== 'nearest'
    ) {
        radiusCircle = L.circle(
            [selectedLocation.lat, selectedLocation.lon],
            {
                radius: Number($('radius').value),
                color: '#789b8b',
                weight: 1.5,
                dashArray: '5 5',
                fillColor: '#a8c7b5',
                fillOpacity: 0.08,
                interactive: false
            }
        ).addTo(map);
    }

    results.forEach((result, index) => {
        const id = String(result.service_id ?? `result-${index}`);

        const distance = formatDistance(result.distance_m);

        const category = result.category || 'Service';
        const subcategory = result.subcategory || '';
        const name = result.name || 'Unnamed service';

        // Popup content is escaped to protect against HTML injection.
        const popup = `
            <div>
                <strong>${esc(name)}</strong>
                <p style="margin:5px 0">
                    ${esc(category)}
                    ${subcategory ? ' · ' + esc(subcategory) : ''}
                </p>
                <p style="margin:5px 0">${esc(distance)} away</p>
                ${result.address
                    ? `<p style="margin:5px 0">${esc(result.address)}</p>`
                    : ''}
                ${result.phone
                    ? `<p style="margin:5px 0">Phone: ${esc(result.phone)}</p>`
                    : ''}
                ${result.opening_hours
                    ? `<p style="margin:5px 0">Hours: ${esc(result.opening_hours)}</p>`
                    : ''}
            </div>
        `;

        const marker = L.marker(
            [result.latitude, result.longitude],
            { icon: serviceIcon }
        ).bindPopup(popup);

        marker.on('click', () => selectResult(id));

        marker.addTo(resultLayer);
        markersById.set(id, marker);

        // Build the result card.
        const card = document.createElement('article');

        card.className = 'result-card';
        card.dataset.id = id;
        card.tabIndex = 0;
        card.setAttribute('role', 'button');
        card.setAttribute(
            'aria-label',
            `Show ${name} on the map`
        );

        card.innerHTML = `
            <div class="result-card-top">
                <span class="result-tag">${esc(category)}</span>
                <span class="result-distance">${esc(distance)}</span>
            </div>

            <h3>${index + 1}. ${esc(name)}</h3>

            ${subcategory
                ? `<p class="result-subcategory">${esc(subcategory)}</p>`
                : ''}

            ${result.address
                ? `<p class="result-address">
                    <span aria-hidden="true">⌖</span>
                    ${esc(result.address)}
                   </p>`
                : ''}

            ${result.phone
                ? `<p class="result-detail">Phone: ${esc(result.phone)}</p>`
                : ''}

            ${result.opening_hours
                ? `<p class="result-detail">
                    Hours: ${esc(result.opening_hours)}
                   </p>`
                : ''}

            <span class="result-action">View on map →</span>
        `;

        card.addEventListener('click', () => selectResult(id));

        card.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectResult(id);
            }
        });

        $('results').appendChild(card);
    });

    if (results.length > 0) {
        message(
            `Showing ${results.length} result(s), sorted by distance.`,
            'success'
        );

        const group = L.featureGroup([...markersById.values()]);

        if (group.getBounds().isValid()) {
            map.fitBounds(
                group.getBounds().pad(0.15),
                { maxZoom: 15 }
            );
        }

        if (originMarker) {
            originMarker.setZIndexOffset(1000);
        }

    } else {
        message(
            data.message ||
            'No matching services found. Try another category or a larger radius.'
        );
    }
}


// ----------------------------------------------------------
// 17. SEARCH BUTTON
// ----------------------------------------------------------

$('search').addEventListener('click', async () => {
    if (!selectedLocation) {
        message(
            'First choose a location by clicking the map, entering coordinates, or using your current location.',
            'error'
        );
        return;
    }

    const radius = Number($('radius').value);
    const limit = Number($('limit').value);

    if (
        !Number.isFinite(radius) ||
        radius < 1 ||
        radius > 100000
    ) {
        message(
            'Radius must be between 1 and 100000 metres.',
            'error'
        );
        return;
    }

    if (
        !Number.isInteger(limit) ||
        limit < 1 ||
        limit > 100
    ) {
        message(
            'Nearest-N must be a whole number between 1 and 100.',
            'error'
        );
        return;
    }

    const button = $('search');

    button.disabled = true;
    button.innerHTML = '<span>Searching…</span><span>…</span>';

    message('Searching nearby services from OpenStreetMap…');

    const query = new URLSearchParams({
        lat: selectedLocation.lat,
        lon: selectedLocation.lon,
        category: $('category').value,
        subcategory: $('subcategory').value,
        mode: $('mode').value,
        radius,
        limit
    });

    try {
        const data = await getJson(
            '/api/search?' + query.toString()
        );

        renderResults(data);

    } catch (error) {
        console.error('Nearby search failed:', error);
        message(error.message, 'error');

    } finally {
        button.disabled = false;

        button.innerHTML = `
            <span>Find nearby services</span>
            <span aria-hidden="true">→</span>
        `;
    }
});


// ----------------------------------------------------------
// 18. START THE APPLICATION
// ----------------------------------------------------------

init();
