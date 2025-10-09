/* eslint-env browser */
/* globals frappe, google */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const statusEl = $("status");
  const { MarkerClusterer } = window.markerClusterer || {};

  let map, usaBounds;
  let leadMarkers = [], publicMarkers = [];
  let leadCluster, publicCluster;

  const STATE_COLORS = {
    Rejected: "#ef4444",
    "Agreement Sent": "#a855f7",
    Approved: "#f59e0b",
    Submitted: "#3b82f6",
    Signed: "#10b981",
    Converted: "#0ea5e9",
    Installed: "#22c55e",
    Draft: "#9ca3af"
  };

  const BRAND_COLOR = "#64748b";

  function setStatus(t) { statusEl.textContent = t || ""; }

  function svgPin(color) {
    const svg = `
      <svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
        <circle cx="16" cy="16" r="12" fill="${color}" fill-opacity="0.15"/>
        <circle cx="16" cy="16" r="8" fill="${color}"/>
      </svg>`;
    return {
      url: "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(svg),
      scaledSize: new google.maps.Size(32, 32),
      anchor: new google.maps.Point(16, 16)
    };
  }

  function leadInfoHtml(f) {
    const address = [f.address, f.city, f.state_name, f.zip].filter(Boolean).join(", ").replace(/</g,"&lt;");
    const company = (f.company || "").replace(/</g,"&lt;");
    const exec = (f.executive_name || "").replace(/</g,"&lt;");
    const st = (f.state || "").replace(/</g,"&lt;");
    const near = f.installed_within_mile && f.nearest_public ?
      `<div class="mt-1"><span class="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-800">ATM within ${f.nearest_public.distance_miles} mi</span>
       <div class="text-slate-600 text-xs mt-1">Nearest: ${(f.nearest_public.name || f.nearest_public.brand || f.nearest_public.operator || "Bitcoin ATM").replace(/</g,"&lt;")}</div></div>`
      : `<div class="mt-1 text-xs text-slate-500">No known ATM within 1 mile</div>`;
    return `
      <div class="text-sm">
        <div class="font-semibold">Lead: ${f.id}</div>
        <div class="text-slate-600">State: <b>${st}</b></div>
        <div class="mt-1">Company: ${company}</div>
        <div class="mt-1">Executive: ${exec}</div>
        <div class="mt-1">${address}</div>
        ${near}
        <div class="mt-1 gmap-badge">Source: Internal</div>
      </div>`;
  }

  function publicInfoHtml(f) {
    const name = (f.name || "Bitcoin ATM").replace(/</g,"&lt;");
    const brand = (f.brand || "").replace(/</g,"&lt;");
    const op = (f.operator || "").replace(/</g,"&lt;");
    const addr = f.address || {};
    const addrLine = [addr.street, addr.housenumber, addr.city, addr.state, addr.postcode].filter(Boolean).join(", ");
    const link = f.website ? `<a class="text-blue-600 underline" href="${f.website}" target="_blank" rel="noopener">Website</a>` : "";
    return `
      <div class="text-sm">
        <div class="font-semibold">${name}</div>
        <div class="text-slate-600">${brand || op || ""}</div>
        <div class="mt-1">${(addrLine || "").replace(/</g,"&lt;")}</div>
        <div class="mt-1">${link}</div>
        <div class="mt-2">
          <button id="btn_create_from_${f.id}" class="h-8 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium">
            Create Prospect
          </button>
        </div>
        <div class="mt-1 gmap-badge">Data © OpenStreetMap contributors</div>
      </div>`;
  }

  function clearMarkers(arr, clusterer) {
    if (clusterer && clusterer.clearMarkers) clusterer.clearMarkers();
    arr.forEach(m => m.setMap && m.setMap(null));
    arr.length = 0;
  }

  function renderList(items) {
    const ul = $("list");
    if (!items.length) {
      ul.innerHTML = `<li class="text-slate-500">No results.</li>`;
      return;
    }
    ul.innerHTML = items.slice(0, 600).map((it, idx) => {
      const label = it.source === "lead" ? `Lead: ${it.id}` : (it.name || it.brand || "Bitcoin ATM");
      const meta = it.source === "lead"
        ? (it.state || "")
        : (it.brand || it.operator || "Public ATM");
      const badge = it.installed_within_mile ? `<span class="ml-2 text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">≤1 mi</span>` : "";
      return `
        <li class="rounded-xl border border-slate-200 p-2 hover:bg-slate-50 cursor-pointer" data-idx="${idx}">
          <div class="flex justify-between items-center">
            <div class="font-medium">${label.replace(/</g,"&lt;")}${badge}</div>
            <div class="text-slate-500 text-xs">${(meta || "").toString().replace(/</g,"&lt;")}</div>
          </div>
        </li>`;
    }).join("");

    Array.from(ul.querySelectorAll("li[data-idx]")).forEach((li) => {
      li.addEventListener("click", () => {
        const idx = Number(li.getAttribute("data-idx"));
        const it = (window.__LIST__ || [])[idx];
        if (it) map.panTo({ lat: it.lat, lng: it.lon });
      });
    });
  }

  function listAll() {
    const items = [];
    if ($("show_leads").checked) items.push(...(window.__LEADS__ || []));
    if ($("show_public").checked) items.push(...(window.__PUBLIC__ || []));
    window.__LIST__ = items;
    renderList(items);
    setStatus(`${items.length} item(s)`);
  }

  async function loadState() {
    const code = $("state_sel").value;
    if (!code) {
      frappe.msgprint("Please choose a US state.");
      return;
    }
    setStatus("Loading state…");
    try {
      const res = await frappe.call({
        method: "cclms.api.atm_map.get_leads_by_state",
        args: { state_code: code, persist_geocode: "false" }
      });
      const { leads, public: pub, bounds } = res.message || { leads: [], public: [], bounds: null };

      // Clear all
      clearMarkers(leadMarkers, leadCluster);
      clearMarkers(publicMarkers, publicCluster);

      window.__LEADS__ = leads || [];
      window.__PUBLIC__ = pub || [];

      // Leads
      if ($("show_leads").checked) {
        for (const f of window.__LEADS__) {
          const color = STATE_COLORS[f.state] || "#6b7280";
          const marker = new google.maps.Marker({
            position: { lat: f.lat, lng: f.lon },
            icon: svgPin(color)
          });
          const iw = new google.maps.InfoWindow({ content: leadInfoHtml(f) });
          marker.addListener("click", () => iw.open({ map, anchor: marker }));
          leadMarkers.push(marker);
        }
        if (MarkerClusterer) {
          leadCluster = new MarkerClusterer({ map, markers: leadMarkers });
        } else {
          leadMarkers.forEach(m => m.setMap(map));
        }
      }

      // Public
      if ($("show_public").checked) {
        for (const f of window.__PUBLIC__) {
          const marker = new google.maps.Marker({
            position: { lat: f.lat, lng: f.lon },
            icon: svgPin(BRAND_COLOR)
          });
          const iw = new google.maps.InfoWindow({ content: publicInfoHtml(f) });
          marker.addListener("click", () => {
            iw.open({ map, anchor: marker });
            // wire the button after open
            setTimeout(() => {
              const btn = document.getElementById(`btn_create_from_${f.id}`);
              if (btn) {
                btn.addEventListener("click", async () => {
                  try {
                    const addr = f.address || {};
                    const r = await frappe.call({
                      method: "cclms.api.atm_map.create_prospect_from_map",
                      args: {
                        name: f.name || f.operator || f.brand,
                        brand: f.brand,
                        operator: f.operator,
                        website: f.website,
                        lat: f.lat,
                        lon: f.lon,
                        address: [addr.street, addr.housenumber].filter(Boolean).join(" "),
                        city: addr.city,
                        state: addr.state,
                        zip: addr.postcode
                      }
                    });
                    frappe.msgprint(`Created ${r.message.doctype}: ${r.message.name}`);
                  } catch (e) {
                    console.error(e);
                    frappe.msgprint("Failed to create prospect.");
                  }
                });
              }
            }, 50);
          });
          publicMarkers.push(marker);
        }
        if (MarkerClusterer) {
          publicCluster = new MarkerClusterer({ map, markers: publicMarkers });
        } else {
          publicMarkers.forEach(m => m.setMap(map));
        }
      }

      // Fit bounds
      if (bounds && bounds.length === 4) {
        const sw = new google.maps.LatLng(bounds[0], bounds[1]);
        const ne = new google.maps.LatLng(bounds[2], bounds[3]);
        map.fitBounds(new google.maps.LatLngBounds(sw, ne));
      }

      listAll();
    } catch (e) {
      console.error(e);
      setStatus("Error");
    }
  }

  async function bootstrap() {
    // populate states
    try {
      const s = await frappe.call({ method: "cclms.api.atm_map.list_us_states" });
      const states = (s.message && s.message.states) || [];
      $("state_sel").innerHTML += states.map(x => `<option value="${x.code}">${x.code} — ${x.name}</option>`).join("");
    } catch (_) {}

    // get Google API key + USA bounds, then load Maps JS
    const cfg = await frappe.call({ method: "cclms.api.atm_map.get_settings" });
    const key = cfg.message.google_maps_api_key;
    const bb = cfg.message.usa_bbox;

    await new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&libraries=maps,marker&v=weekly`;
      script.async = true;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });

    const sw = new google.maps.LatLng(bb[0], bb[1]);
    const ne = new google.maps.LatLng(bb[2], bb[3]);
    usaBounds = new google.maps.LatLngBounds(sw, ne);

    map = new google.maps.Map(document.getElementById("map"), {
      center: { lat: 37.8, lng: -96.9 },
      zoom: 4,
      restriction: { latLngBounds: usaBounds, strictBounds: false },
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false
    });

    $("btn_load").addEventListener("click", loadState);
    $("show_leads").addEventListener("change", loadState);
    $("show_public").addEventListener("change", loadState);

    // Show just the USA map initially; user picks state to load data
    setStatus("Pick a state to load markers.");
  }

  frappe.ready(() => {
    bootstrap().catch((e) => {
      console.error(e);
      frappe.msgprint("Failed to load Google Maps. Check your API key.");
    });
  });
})();
