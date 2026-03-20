// www/atm-radar/index.js
/* global frappe */
(function () {
  "use strict";

  let map = null;
  let info = null;
  let placesService = null;
  let markers = [];

  function qs(id) { return document.getElementById(id); }
  function val(id) { return (qs(id)?.value || "").trim(); }
  function mapEl() { return qs("map") || qs("atm-map"); }
  function setMeta(html) { const el = qs("meta") || qs("atm-map-legend"); if (el) el.innerHTML = html; }
  function clearMarkers() { markers.forEach((m) => m.setMap(null)); markers = []; }
  function escapeHtml(value) { return frappe.utils.escape_html(String(value || "")); }

  function usaBounds() {
    return new google.maps.LatLngBounds(
      { lat: 24.7433195, lng: -124.7844079 },
      { lat: 49.3457868, lng: -66.9513812 }
    );
  }

  async function fetchGmapsKey() {
    const res = await frappe.call({ method: "cclms.api.atm_radar.get_google_maps_key" });
    return res?.message?.api_key;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.defer = true;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  async function initMap() {
    const key = await fetchGmapsKey();
    if (!key) {
      frappe.msgprint("Google Maps key missing. Ask admin to fill Google Maps Settings.");
      return;
    }

    const callbackName = "gmapsInit_" + Date.now();
    window[callbackName] = () => {
      const target = mapEl();
      if (!target) {
        frappe.msgprint("Map container not found.");
        return;
      }

      map = new google.maps.Map(target, {
        center: { lat: 39.8283, lng: -98.5795 },
        zoom: 4,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
      });
      info = new google.maps.InfoWindow();
      placesService = new google.maps.places.PlacesService(map);
      map.fitBounds(usaBounds());
      map.addListener("click", (event) => inspectPlace(event.latLng));
      runQuery();
    };

    const src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&libraries=places&callback=${callbackName}`;
    await loadScript(src);
  }

  async function getLeads(args) {
    try {
      const res = await frappe.call({
        method: "cclms.api.atm_radar.get_leads_by_state",
        args,
      });
      return res?.message || { rows: [], meta: {} };
    } catch (error) {
      console.error("[ATM Radar] API error", error);
      frappe.msgprint({ title: "API Error", message: "Failed to load leads", indicator: "red" });
      return { rows: [], meta: {} };
    }
  }

  function markerIconByStatus(status) {
    const s = (status || "").toLowerCase();
    if (s.includes("installed")) return "http://maps.google.com/mapfiles/ms/icons/green-dot.png";
    if (s.includes("converted")) return "http://maps.google.com/mapfiles/ms/icons/ltblue-dot.png";
    if (s.includes("signed")) return "http://maps.google.com/mapfiles/ms/icons/blue-dot.png";
    if (s.includes("agreement")) return "http://maps.google.com/mapfiles/ms/icons/yellow-dot.png";
    if (s.includes("approved")) return "http://maps.google.com/mapfiles/ms/icons/purple-dot.png";
    if (s.includes("rejected")) return "http://maps.google.com/mapfiles/ms/icons/red-dot.png";
    return "http://maps.google.com/mapfiles/ms/icons/orange-dot.png";
  }

  function openLeadInfo(marker, row) {
    const addr = [
      row.address,
      [row.city, row.state, row.zip_code].filter(Boolean).join(", "),
      row.country,
    ].filter(Boolean).join("<br>");

    info.setContent(`
      <div class="text-sm">
        <div class="font-semibold">${escapeHtml(row.company || "—")}</div>
        <div class="text-gray-600">${escapeHtml(row.workflow_state || "—")}</div>
        <div class="mt-1">${addr}</div>
        <div class="mt-1 text-gray-500">Executive: ${escapeHtml(row.executive_name || "—")}</div>
        <div class="mt-2 flex gap-2">
          <a class="px-3 py-1 rounded-lg bg-gray-100 hover:bg-gray-200"
             href="/app/atm-leads/${encodeURIComponent(row.name)}" target="_blank" rel="noopener">Open Lead</a>
        </div>
      </div>
    `);
    info.open({ anchor: marker, map });
  }

  function drawMarkers(rows) {
    clearMarkers();
    if (!map || !rows?.length) return;

    const bounds = new google.maps.LatLngBounds();
    rows.forEach((row) => {
      const lat = Number(row.latitude);
      const lng = Number(row.longitude);
      if (Number.isNaN(lat) || Number.isNaN(lng)) return;

      const marker = new google.maps.Marker({
        position: { lat, lng },
        map,
        title: row.company || row.name,
        icon: markerIconByStatus(row.workflow_state),
      });
      marker.addListener("click", () => openLeadInfo(marker, row));
      markers.push(marker);
      bounds.extend(marker.getPosition());
    });

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds);
      const listener = google.maps.event.addListenerOnce(map, "bounds_changed", () => {
        if (map.getZoom() > 12) map.setZoom(12);
      });
      setTimeout(() => google.maps.event.removeListener(listener), 2000);
    }
  }

  function updateMeta(meta, count) {
    const s = meta?.state ? `State <b>${escapeHtml(meta.state)}</b>` : "All USA";
    const c = meta?.company ? ` | Company <b>${escapeHtml(meta.company)}</b>` : "";
    const e = meta?.executive_name ? ` | Executive <b>${escapeHtml(meta.executive_name)}</b>` : "";
    const q = meta?.queried ?? 0;
    const w = meta?.with_coordinates ?? 0;
    setMeta(`${s}${c}${e} &nbsp; — &nbsp; Queried: ${q}, With coordinates: ${w}, Plotted: ${count}`);
  }

  async function reverseGeocode(latLng) {
    const geocoder = new google.maps.Geocoder();
    const result = await geocoder.geocode({ location: latLng }).catch(() => null);
    const first = result?.results?.[0];
    if (!first) return null;

    const components = first.address_components || [];
    const getComp = (type, key = "long_name") => (components.find((x) => x.types.includes(type)) || {})[key] || "";

    return {
      formatted_address: first.formatted_address || "",
      street_address: [getComp("street_number"), getComp("route")].filter(Boolean).join(" ").trim(),
      city: getComp("locality") || getComp("postal_town"),
      state_code: getComp("administrative_area_level_1", "short_name"),
      zip_code: getComp("postal_code"),
      country: getComp("country"),
    };
  }

  async function nearestPlace(latLng) {
    if (!placesService) return null;

    const nearby = await new Promise((resolve) => {
      placesService.nearbySearch(
        { location: latLng, radius: 80, rankBy: google.maps.places.RankBy.PROMINENCE },
        (rows, status) => resolve(status === google.maps.places.PlacesServiceStatus.OK ? rows : [])
      );
    });
    if (!nearby.length || !nearby[0]?.place_id) return null;

    return new Promise((resolve) => {
      placesService.getDetails(
        { placeId: nearby[0].place_id, fields: ["place_id", "name", "formatted_address", "url", "types"] },
        (row, status) => resolve(status === google.maps.places.PlacesServiceStatus.OK ? row : null)
      );
    });
  }

  function callApi(method, args) {
    return frappe.call({ method, args }).then((r) => r?.message || {});
  }

  async function inspectPlace(latLng) {
    const geocode = await reverseGeocode(latLng);
    const place = await nearestPlace(latLng);

    const payload = {
      place_id: place?.place_id || "",
      display_name: place?.name || "",
      address: geocode?.street_address || geocode?.formatted_address || place?.formatted_address || "",
      city: geocode?.city || "",
      state_code: geocode?.state_code || "",
      zip_code: geocode?.zip_code || "",
      actual_zip_code: geocode?.zip_code || "",
      country: geocode?.country || "",
      latitude: latLng.lat(),
      longitude: latLng.lng(),
      source: place?.url || "btm-radar",
      provider: "Google Maps",
      brand: place?.name || "Unknown",
    };

    const lookup = await callApi("cclms.api.competitor_kiosk_helper.lookup_competitor_kiosk", payload);
    renderCompetitorInfo(latLng, place, geocode, lookup, payload);
  }

  function renderCompetitorInfo(latLng, place, geocode, lookup, payload) {
    const existing = lookup?.existing || null;
    const allowed = lookup?.allowed !== false;
    const wrapper = document.createElement("div");
    wrapper.style.minWidth = "300px";
    wrapper.innerHTML = `
      <div class="text-sm">
        <div class="font-semibold">${escapeHtml(place?.name || geocode?.street_address || "Selected Location")}</div>
        <div class="mt-1">${escapeHtml(geocode?.formatted_address || place?.formatted_address || payload.address)}</div>
        ${payload.zip_code ? `<div class="mt-1">ZIP: <b>${escapeHtml(payload.zip_code)}</b></div>` : ""}
        ${payload.country ? `<div class="mt-1">Country: <b>${escapeHtml(payload.country)}</b></div>` : ""}
        ${allowed ? "" : `<div class="mt-2 text-red-600"><b>${escapeHtml(lookup?.message || "Only USA locations can be saved")}</b></div>`}
        ${existing ? `
          <div class="mt-2 p-2 rounded" style="background:#fef3c7;border:1px solid #f59e0b;">
            <div><b>Competitor kiosk already exists</b></div>
            <div>${escapeHtml(existing.display_name || existing.brand || existing.name)}</div>
            <div>Reason: ${escapeHtml(existing.duplicate_reason || "duplicate")}</div>
          </div>
        ` : allowed ? `
          <div class="mt-2 p-2 rounded" style="background:#ecfdf5;border:1px solid #10b981;">
            <div><b>No competitor duplicate found</b></div>
            <div>Save this USA place as Competitor Kiosk.</div>
          </div>
        ` : ""}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">
          ${allowed ? `<button class="btn btn-sm btn-primary" data-action="save-kiosk">${existing ? "Update Competitor Kiosk" : "Create Competitor Kiosk"}</button>` : ""}
          ${existing ? `<a class="btn btn-sm btn-default" href="/app/competitor-kiosk/${encodeURIComponent(existing.name)}" target="_blank" rel="noopener">Open Competitor Kiosk</a>` : ""}
          ${place?.url ? `<a class="btn btn-sm btn-default" href="${place.url}" target="_blank" rel="noopener">Open in Google Maps</a>` : ""}
        </div>
      </div>
    `;

    const saveButton = wrapper.querySelector("[data-action='save-kiosk']");
    if (saveButton) {
      saveButton.addEventListener("click", async () => {
        const result = await callApi("cclms.api.competitor_kiosk_helper.upsert_competitor_kiosk_from_radar", payload);
        frappe.show_alert({
          message: result.created ? __("Competitor kiosk created: {0}", [result.name]) : __("Competitor kiosk updated: {0}", [result.name]),
          indicator: "green",
        });
      });
    }

    info.setContent(wrapper);
    info.setPosition(latLng);
    info.open({ map });
  }

  async function runQuery() {
    const args = {
      state: val("state_input") || null,
      company: val("company_input") || null,
      executive_name: val("exec_input") || null,
      status_in: val("status_input") || null,
    };

    const res = await getLeads(args);
    drawMarkers(res.rows);
    updateMeta(res.meta, (res.rows || []).length);
  }

  function resetUI() {
    ["state_input", "company_input", "exec_input", "status_input"].forEach((id) => {
      const el = qs(id);
      if (el) el.value = "";
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const applyBtn = qs("apply_btn");
    const resetBtn = qs("reset_btn");

    if (applyBtn) applyBtn.addEventListener("click", runQuery);
    if (resetBtn) {
      resetBtn.addEventListener("click", async () => {
        resetUI();
        await runQuery();
      });
    }

    initMap();
  });
})();
