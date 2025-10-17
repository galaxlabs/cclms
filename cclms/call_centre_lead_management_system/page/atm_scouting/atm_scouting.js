// frappe.pages['atm_scouting'].on_page_load = function(wrapper) {
// 	var page = frappe.ui.make_app_page({
// 		parent: wrapper,
// 		title: 'Atm Scouting',
// 		single_column: true
// 	});
// 	page.set_primary_action(__('New'), function() {
// 		frappe.new_doc('ATM Scouting');
// 	});
// };

frappe.provide("cclms.pages.atm_scouting");

frappe.pages['atm_scouting'].on_page_load = function(wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'ATM Scouting',
    single_column: true
  });

  // inline HTML to avoid template issues
  $(`
    <div class="atm-scouting" style="display:flex; gap:12px;">
      <div style="flex:1 1 auto; min-width:60%;">
        <div id="atm-map" style="height: calc(100vh - 220px); width: 100%; border-radius:8px; border:1px solid var(--border-color);"></div>
        <div style="margin-top:8px; display:flex; gap:16px; flex-wrap:wrap;">
          <span><b>Zones:</b></span>
          <span style="color:#16a34a;">● Green</span>
          <span style="color:#86efac;">● Light Green</span>
          <span style="color:#facc15;">● Yellow</span>
          <span style="color:#ef4444;">● Red</span>
          <span style="color:#9ca3af;">● Unclassified</span>
        </div>
      </div>
      <div style="flex:0 0 380px;">
        <div style="display:flex; gap:8px; margin-bottom:8px;">
          <input id="search_box" class="input-with-feedback form-control" placeholder="Search name / zip / type" />
          <button id="refresh_btn" class="btn btn-default btn-sm">Refresh</button>
        </div>
        <div style="display:flex; gap:8px; margin-bottom:8px; flex-wrap:wrap;">
          <select id="wf_filter" class="form-control">
            <option value="">All Statuses</option>
            <option>Draft</option><option>Submitted</option><option>Approved</option>
            <option>Signed</option><option>Installed</option><option>Rejected</option>
          </select>
          <select id="zone_filter" class="form-control">
            <option value="">All Zones</option>
            <option>Green</option><option>Light Green</option><option>Yellow</option>
            <option>Red</option><option>Unclassified</option>
          </select>
          <label style="display:flex;align-items:center;gap:6px;">
            <input type="checkbox" id="show_zone_circles" checked /> Show zone circles
          </label>
        </div>
        <div id="list_container" style="height: calc(100vh - 260px); overflow:auto; border:1px solid var(--border-color); border-radius:8px; padding:8px;"></div>
      </div>
    </div>
  `).appendTo(page.body);

  cclms.pages.atm_scouting.controller = new ATMScoutingController(wrapper);
};

class ATMScoutingController {
  constructor(wrapper) {
    this.wrapper = wrapper;
    this.map = null;
    this.markers = [];
    this.circles = [];
    this.leads = [];
    this.zones = [];
    this.google_key = null;

    this.$list = $(wrapper).find('#list_container');
    this.$search = $(wrapper).find('#search_box');
    this.$wf = $(wrapper).find('#wf_filter');
    this.$zone = $(wrapper).find('#zone_filter');
    this.$refresh = $(wrapper).find('#refresh_btn');
    this.$showZones = $(wrapper).find('#show_zone_circles');

    this.$search.on('input', () => this._renderList());
    this.$wf.on('change', () => { this._renderMarkers(); this._renderList(); });
    this.$zone.on('change', () => { this._renderMarkers(); this._renderList(); });
    this.$refresh.on('click', () => this._loadData(true));
    this.$showZones.on('change', () => this._renderZoneCircles());

    this._boot();
  }

  async _boot() {
    try {
      const r = await frappe.call({ method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_google_maps_key" });
      this.google_key = r.message && r.message.api_key;
      if (!this.google_key) throw new Error("Google Maps API key missing in Google Maps Settings.");

      await this._loadGoogleMaps();
      this._initMap();
      await this._loadData(true);
    } catch (e) {
      console.error(e);
      frappe.msgprint({title:"Map Error", message: e.message || e});
    }
  }

  _loadGoogleMaps() {
    return new Promise((resolve, reject) => {
      if (window.google && google.maps) return resolve();
      const s = document.createElement('script');
      s.src = `https://maps.googleapis.com/maps/api/js?key=${this.google_key}&libraries=places`;
      s.async = true; s.defer = true;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("Failed to load Google Maps JS"));
      document.head.appendChild(s);
    });
  }

  _initMap() {
    this.map = new google.maps.Map(document.getElementById('atm-map'), {
      center: { lat: 37.8, lng: -96 },
      zoom: 5,
      streetViewControl: false,
      fullscreenControl: true
    });
    this.map.addListener('click', (e) => this._onMapClick(e.latLng));
  }

  async _loadData(fitBounds=false) {
    const leadsResp = await frappe.call({ method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_leads_for_map" });
    this.leads = (leadsResp.message || []).filter(x => x.latitude && x.longitude);

    const zonesResp = await frappe.call({ method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_zone_circles" });
    this.zones = zonesResp.message || [];

    this._renderMarkers(fitBounds);
    this._renderZoneCircles();
    this._renderList();
  }

  _markerColorByZone(zone) {
    const map = {
      "Green": "#16a34a",
      "Light Green": "#86efac",
      "Yellow": "#facc15",
      "Red": "#ef4444",
      "Unclassified": "#9ca3af"
    };
    return map[zone || "Unclassified"] || "#9ca3af";
  }

  _markerIcon(color) {
    return {
      path: "M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2z",
      fillColor: color, fillOpacity: 0.9,
      strokeColor: "#1f2937", strokeWeight: 1, scale: 1
    };
  }

  _renderMarkers(fitBounds=false) {
    // clear
    this.markers.forEach(m => m.setMap(null));
    this.markers = [];

    const wf = (this.$wf.val() || "").toLowerCase();
    const zf = (this.$zone.val() || "").toLowerCase();

    const filtered = this.leads.filter(l => {
      const wfOk = !wf || (l.workflow_state || "").toLowerCase() === wf;
      const zOk = !zf || (l.zone || "").toLowerCase() === zf;
      return wfOk && zOk;
    });

    const bounds = new google.maps.LatLngBounds();

    filtered.forEach(lead => {
      const color = this._markerColorByZone(lead.zone);
      const marker = new google.maps.Marker({
        position: { lat: lead.latitude, lng: lead.longitude },
        map: this.map,
        title: lead.business_name || lead.name,
        icon: this._markerIcon(color)
      });

      const html = `
        <div style="min-width:220px">
          <b>${frappe.utils.escape_html(lead.business_name || lead.name)}</b><br>
          <div>Type: ${frappe.utils.escape_html(lead.business_type || '')}</div>
          <div>ZIP: ${frappe.utils.escape_html(lead.zip || '')}</div>
          <div>Status: ${frappe.utils.escape_html(lead.workflow_state || '')}</div>
          <div>Zone: <span style="color:${color};font-weight:600">${frappe.utils.escape_html(lead.zone || 'Unclassified')}</span></div>
          ${lead.score !== undefined ? `<div>Score: ${lead.score}</div>` : ``}
          <div style="margin-top:6px;">
            <a class="btn btn-xs btn-default" href="/app/atm-leads/${encodeURIComponent(lead.name)}" target="_blank">Open Lead</a>
          </div>
        </div>
      `;
      const iw = new google.maps.InfoWindow({ content: html });
      marker.addListener('click', () => iw.open(this.map, marker));
      this.markers.push(marker);
      bounds.extend(marker.getPosition());
    });

    if (fitBounds && filtered.length) this.map.fitBounds(bounds);
  }

  _renderZoneCircles() {
    this.circles.forEach(c => c.setMap(null));
    this.circles = [];
    if (!this.$showZones.is(":checked")) return;

    const ok = new Set(["Green","Light Green","Yellow"]);
    (this.zones || []).forEach(z => {
      if (!z.latitude || !z.longitude) return;
      if (!ok.has(z.zone)) return;
      const color = this._markerColorByZone(z.zone);
      const circle = new google.maps.Circle({
        strokeColor: color, strokeOpacity: 0.9, strokeWeight: 1,
        fillColor: color, fillOpacity: 0.18,
        map: this.map,
        center: { lat: z.latitude, lng: z.longitude },
        radius: z.radius_meters || 8000
      });
      const iw = new google.maps.InfoWindow({
        content: `
          <div><b>ZIP ${frappe.utils.escape_html(z.zip_code || '')}</b></div>
          <div>Zone: <span style="color:${color};font-weight:600">${frappe.utils.escape_html(z.zone || '')}</span></div>
          ${z.population ? `<div>Population: ${z.population}</div>` : ``}
          ${z.margin ? `<div>Margin: ${z.margin}</div>` : ``}
          ${z.competitor_kiosks !== undefined ? `<div>Competitors: ${z.competitor_kiosks}</div>` : ``}
        `
      });
      circle.addListener('click', (evt) => { iw.setPosition(evt.latLng); iw.open(this.map); });
      this.circles.push(circle);
    });
  }

  _renderList() {
    const q = (this.$search.val() || "").toLowerCase();
    const wf = (this.$wf.val() || "").toLowerCase();
    const zf = (this.$zone.val() || "").toLowerCase();

    const filtered = this.leads.filter(l => {
      const s = `${l.name} ${l.business_name||''} ${l.business_type||''} ${l.zip||''}`.toLowerCase();
      const qok = !q || s.includes(q);
      const wfOk = !wf || (l.workflow_state || "").toLowerCase() === wf;
      const zOk = !zf || (l.zone || "").toLowerCase() === zf;
      return qok && wfOk && zOk;
    });

    const html = filtered.map(l => {
      const color = this._markerColorByZone(l.zone);
      return `
        <div style="border-bottom:1px solid var(--border-color); padding:6px 2px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
              <div style="font-weight:600;">${frappe.utils.escape_html(l.business_name || l.name)}</div>
              <div style="font-size:12px; opacity:.8;">${frappe.utils.escape_html(l.business_type || '')} • ZIP ${frappe.utils.escape_html(l.zip || '')}</div>
              <div style="font-size:12px;">Status: ${frappe.utils.escape_html(l.workflow_state || '')} • Zone: <span style="color:${color}; font-weight:600">${frappe.utils.escape_html(l.zone || 'Unclassified')}</span> ${l.score !== undefined ? `• Score: ${l.score}` : ''}</div>
            </div>
            <div><a class="btn btn-xs btn-default" href="/app/atm-leads/${encodeURIComponent(l.name)}" target="_blank">Open</a></div>
          </div>
        </div>
      `;
    }).join("") || `<div class="text-muted">No leads found for current filters.</div>`;

    this.$list.html(html);
  }

  async _onMapClick(latlng) {
    try {
      const resp = await fetch(`https://maps.googleapis.com/maps/api/geocode/json?latlng=${latlng.lat()},${latlng.lng()}&key=${this.google_key}`);
      const data = await resp.json();
      const addr = data?.results?.[0]?.formatted_address || 'Unknown';
      const zip = (data?.results?.[0]?.address_components || []).find(c => c.types.includes("postal_code"))?.long_name;

      // quick client duplicate check (~50m)
      const dup = this.leads.find(l => this._haversine(l.latitude,l.longitude,latlng.lat(),latlng.lng()) <= 0.05);
      const dupMsg = dup ? `<div style="color:#b91c1c; font-weight:600; margin-top:4px;">Possible duplicate: ${frappe.utils.escape_html(dup.business_name || dup.name)} (${dup.workflow_state})</div>` : ``;

      frappe.msgprint({
        title: "Create lead here?",
        message: `<div><b>${frappe.utils.escape_html(addr)}</b></div><div>ZIP: ${frappe.utils.escape_html(zip || '')}</div>${dupMsg}`,
        primary_action: {
          label: dup ? "Open Existing Lead" : "Create ATM Lead",
          action: async () => {
            if (dup) { window.open(`/app/atm-leads/${encodeURIComponent(dup.name)}`,"_blank"); frappe.hide_msgprint(); return; }
            const r = await frappe.call({
              method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.create_lead_from_map",
              args: { lat: latlng.lat(), lng: latlng.lng(), formatted_address: addr, zip: zip || "" }
            });
            frappe.hide_msgprint();
            if (r.message && r.message.name) {
              frappe.show_alert({message:`Lead created: ${r.message.name}`, indicator:'green'});
              window.open(`/app/atm-leads/${encodeURIComponent(r.message.name)}`,"_blank");
              this._loadData();
            }
          }
        }
      });
    } catch (e) { console.error(e); }
  }

  _haversine(lat1, lon1, lat2, lon2) {
    function rad(x){ return x*Math.PI/180; }
    const R=6371, dLat=rad(lat2-lat1), dLon=rad(lon2-lon1);
    const a = Math.sin(dLat/2)**2 + Math.cos(rad(lat1))*Math.cos(rad(lat2))*Math.sin(dLon/2)**2;
    return 2*R*Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); // km
  }
}
