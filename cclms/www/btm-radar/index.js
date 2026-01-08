// www/atm-radar/index.js
/* global frappe */
(function () {
  "use strict";

  /** @type {google.maps.Map|null} */
  let map = null;
  /** @type {google.maps.InfoWindow|null} */
  let info = null;
  /** @type {google.maps.Marker[]} */
  let markers = [];

  // --- UI helpers -----------------------------------------------------------

  function qs(id) { return document.getElementById(id); }
  function val(id) { return (qs(id)?.value || "").trim(); }
  function setMeta(html) { const el = qs("meta"); if (el) el.innerHTML = html; }
  function clearMarkers() { markers.forEach(m => m.setMap(null)); markers = []; }

  function usaBounds() {
    // Rough USA bounding box
    const sw = { lat: 24.7433195, lng: -124.7844079 };
    const ne = { lat: 49.3457868, lng: -66.9513812 };
    return new google.maps.LatLngBounds(sw, ne);
  }

  // --- Google Maps loader ---------------------------------------------------

  async function fetchGmapsKey() {
    // Requires authenticated user (we purposely do not expose key to guests)
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
    // Always render the map first, even if we fail to load data.
    const key = await fetchGmapsKey();
    if (!key) {
      frappe.msgprint("Google Maps key missing. Ask admin to fill Google Maps Settings.");
      return;
    }

    const callbackName = "gmapsInit_" + Date.now();
    window[callbackName] = () => {
      map = new google.maps.Map(qs("map"), {
        center: { lat: 39.8283, lng: -98.5795 }, // USA center
        zoom: 4,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true
      });
      info = new google.maps.InfoWindow();
      // Try to keep initial viewport to USA bounds
      map.fitBounds(usaBounds());
      // After map exists, load data
      runQuery();
    };

    const src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&callback=${callbackName}`;
    await loadScript(src);
  }

  // --- Data fetching --------------------------------------------------------

  async function getLeads(args) {
    try {
      const res = await frappe.call({
        method: "cclms.api.atm_radar.get_leads_by_state",
        args
      });
      return res?.message || { rows: [], meta: {} };
    } catch (e) {
      const j = e?.xhr?.responseJSON;
      console.error("[ATM Radar] API error", j || e);
      frappe.msgprint({ title: "API Error", message: "Failed to load leads", indicator: "red" });
      return { rows: [], meta: {} };
    }
  }

  function markerIconByStatus(status) {
    const s = (status || "").toLowerCase();
    // simple colored default pin variants
    if (s.includes("installed")) return "http://maps.google.com/mapfiles/ms/icons/green-dot.png";
    if (s.includes("converted")) return "http://maps.google.com/mapfiles/ms/icons/ltblue-dot.png";
    if (s.includes("signed")) return "http://maps.google.com/mapfiles/ms/icons/blue-dot.png";
    if (s.includes("agreement")) return "http://maps.google.com/mapfiles/ms/icons/yellow-dot.png";
    if (s.includes("approved")) return "http://maps.google.com/mapfiles/ms/icons/purple-dot.png";
    if (s.includes("rejected")) return "http://maps.google.com/mapfiles/ms/icons/red-dot.png";
    return "http://maps.google.com/mapfiles/ms/icons/orange-dot.png";
  }

  function openInfo(marker, row) {
    const addr = [
      row.address,
      [row.city, row.state, row.zip_code].filter(Boolean).join(", "),
      row.country
    ].filter(Boolean).join("<br>");

    const html = `
      <div class="text-sm">
        <div class="font-semibold">${frappe.utils.escape_html(row.company || "—")}</div>
        <div class="text-gray-600">${frappe.utils.escape_html(row.workflow_state || "—")}</div>
        <div class="mt-1">${addr}</div>
        <div class="mt-1 text-gray-500">Executive: ${frappe.utils.escape_html(row.executive_name || "—")}</div>
        <div class="mt-2 flex gap-2">
          <a class="px-3 py-1 rounded-lg bg-gray-100 hover:bg-gray-200"
             href="/app/atm-leads/${encodeURIComponent(row.name)}" target="_blank" rel="noopener">Open Lead</a>
          ${row.company ? `<a class="px-3 py-1 rounded-lg bg-gray-100 hover:bg-gray-200" href="/app/operator-companies/${encodeURIComponent(row.company)}" target="_blank" rel="noopener">Open Company</a>` : ""}
          ${row.executive_name ? `<a class="px-3 py-1 rounded-lg bg-gray-100 hover:bg-gray-200" href="/app/sales-agent/${encodeURIComponent(row.executive_name)}" target="_blank" rel="noopener">Open Executive</a>` : ""}
        </div>
      </div>
    `;
    info.setContent(html);
    info.open({ anchor: marker, map });
  }

  function drawMarkers(rows) {
    clearMarkers();
    if (!map || !rows || !rows.length) return;

    const bounds = new google.maps.LatLngBounds();
    rows.forEach((r) => {
      const lat = Number(r.latitude);
      const lng = Number(r.longitude);
      if (Number.isNaN(lat) || Number.isNaN(lng)) return;

      const m = new google.maps.Marker({
        position: { lat, lng },
        map,
        title: r.company || r.name,
        icon: markerIconByStatus(r.workflow_state)
      });
      m.addListener("click", () => openInfo(m, r));
      markers.push(m);
      bounds.extend(m.getPosition());
    });

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds);
      // prevent zooming too far
      const listener = google.maps.event.addListenerOnce(map, "bounds_changed", function () {
        if (map.getZoom() > 12) map.setZoom(12);
      });
      // just in case
      setTimeout(() => google.maps.event.removeListener(listener), 2000);
    }
  }

  function updateMeta(meta, count) {
    const s = meta?.state ? `State <b>${frappe.utils.escape_html(meta.state)}</b>` : "All USA";
    const c = meta?.company ? ` | Company <b>${frappe.utils.escape_html(meta.company)}</b>` : "";
    const e = meta?.executive_name ? ` | Executive <b>${frappe.utils.escape_html(meta.executive_name)}</b>` : "";
    const q = meta?.queried ?? 0;
    const w = meta?.with_coordinates ?? 0;
    setMeta(`${s}${c}${e} &nbsp; — &nbsp; Queried: ${q}, With coordinates: ${w}, Plotted: ${count}`);
  }

  // --- Query runner ---------------------------------------------------------

  async function runQuery() {
    const args = {
      state: val("state_input") || null,
      company: val("company_input") || null,
      executive_name: val("exec_input") || null,
      status_in: val("status_input") || null
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

  // --- Wire up --------------------------------------------------------------

  document.addEventListener("DOMContentLoaded", () => {
    // Buttons
    const applyBtn = qs("apply_btn");
    const resetBtn = qs("reset_btn");

    if (applyBtn) applyBtn.addEventListener("click", runQuery);
    if (resetBtn) resetBtn.addEventListener("click", async () => {
      resetUI();
      await runQuery();
    });

    // Initialize map then query
    initMap();
  });
})();
