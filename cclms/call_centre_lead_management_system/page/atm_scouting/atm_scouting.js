frappe.provide("cclms.pages.atm_scouting");

frappe.pages['atm_scouting'].on_page_load = function(wrapper){
  const page = frappe.ui.make_app_page({ parent: wrapper, title: 'ATM Scouting (Global)', single_column: true });
  $(frappe.render_template("atm_scouting", {})).appendTo(page.body);
  cclms.pages.atm_scouting.ctrl = new ATMScoutingGM(wrapper);
};

class ATMScoutingGM {
  constructor(wrapper){
    this.w = wrapper;
    this.map = null;
    this.googleKey = null;
    this.mapId = null;

    this.leads = [];         // from server
    this.leadMarkers = [];   // google.advanced markers
    this.markerById = {};    // name -> marker
    this.zipCircles = [];    // google.maps.Circle[]
    this.comps = [];         // competitor markers
    this.compData = [];      // competitor rows
    this.filteredLeads = []; // after client-side filtering

    this._debouncedReloadInView = this._debounce(() => this._reloadLeadsInView(), 250);
    this._bindUI();
    this._boot();
  }


  _debounce(fn, ms){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn.apply(this,a), ms); }; }

  _bindUI(){
    
    this.$viewportOnly = $(this.w).find('#viewport_only');
    this.$viewportOnly.on('change', () => {
      if (this.$viewportOnly.is(':checked')) {
        this._reloadLeadsInView();
      } else {
         this.leads = [...(this.allLeads || [])];
          this._drawLeadMarkers(false).then(() => this._applyLeadFilters());
      }
    });

    this.$q = $(this.w).find('#q');
    this.$wf = $(this.w).find('#wf');
    this.$toggleZip = $(this.w).find('#toggle_zip');
    this.$toggleComp = $(this.w).find('#toggle_comp');
    this.$btnRefresh = $(this.w).find('#btn_refresh');
    this.$btnInstalled = $(this.w).find('#btn_installed');
    this.$btnSigned = $(this.w).find('#btn_signed');
    this.$btnBackfill = $(this.w).find('#btn_backfill');
    this.$onlyUS = $(this.w).find('#only_us');
    this.$nonRed = $(this.w).find('#non_red');

    this.$q.on('input', () => { this._applyLeadFilters(); this._debouncedReloadInView(); });
    this.$wf.on('change', () => this._applyLeadFilters());
    this.$toggleZip.on('change', () => this._showHideZipCircles());
    this.$toggleComp.on('change', () => this._reloadCompetitors());
    this.$btnRefresh.on('click', () => this._loadAll(true));
    

    this.$onlyUS.on('change', () => this._loadAll(true));
    this.$nonRed.on('change', () => this._loadAll(true));

    this.$btnInstalled.on('click', () => { this.$wf.val('Installed'); this._applyLeadFilters(); });
    this.$btnSigned.on('click', () => { this.$wf.val('Signed'); this._applyLeadFilters(); });

    this.$btnBackfill.on('click', async () => {
      try{
        frappe.show_alert({message: "Backfilling missing ZIP centroids…", indicator: "blue"});
        const r = await frappe.call({ method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.geocode_missing_zip_centroids" });
        frappe.show_alert({message: `Geocoded: ${r.message?.updated||0}`, indicator: "green"});
        await this._loadAll(); // refresh circles
      }catch(e){ frappe.msgprint("Backfill failed: "+String(e)); }
    });
  }

  async _boot(){
    try{
      const r = await frappe.call({ method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_google_maps_settings" });
      this.googleKey = r.message?.api_key || null;
      this.mapId     = r.message?.map_id  || null;
      if (!this.googleKey) throw new Error("Google Maps API key not configured.");

      await this._loadGoogle();
      await this._initMap();
      await this._loadAll(true);

      // reload viewport overlays
      this.map.addListener('idle', () => {
        this._reloadLeadsInView();
        if (this.$toggleComp.is(':checked')) this._reloadCompetitors();
      });
    } catch(e){
      console.error(e);
      frappe.msgprint({title:"Map init failed", message: String(e)});
    }
  }

  async _loadGoogle(){
    await new Promise((resolve, reject) => {
      if (window.google && google.maps) return resolve();
      const s = document.createElement('script');
      s.src = `https://maps.googleapis.com/maps/api/js?key=${this.googleKey}&v=weekly&libraries=places,marker`;
      s.async = true; s.defer = true;
      s.onload = resolve; s.onerror = () => reject(new Error("Google JS load failed"));
      document.head.appendChild(s);
    });
    if (!google.maps.importLibrary) throw new Error("importLibrary API unavailable (use v=weekly)");
  }

  async _initMap(){
    const { Map } = await google.maps.importLibrary("maps");
    const NA_BOUNDS = { north: 83.0, south: 7.0, west: -170.0, east: -52.0 };

    this.map = new Map(document.getElementById('gm-map'), {
      center: { lat: 39.5, lng: -98.35 },
      zoom: 4.5,
      minZoom: 3,
      maxZoom: 18,
      restriction: { latLngBounds: NA_BOUNDS, strictBounds: false }, // “global”—you can relax this later if you expand
      mapId: this.mapId || undefined,
      streetViewControl: false,
      fullscreenControl: true,
      mapTypeControl: true,
    });

    // click → inspect (no create)
    this.map.addListener('click', (e) => this._inspectLocation(e.latLng));
  }

  async _loadAll(fit=false){
  const leadsResp = await frappe.call({
    method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_leads_non_red",
    args: {
      filter_non_red: 0,   // ← show ALL (was 1)
      us_only: 0       
    }
  });
  this.leads = (leadsResp.message || []).filter(x => x.latitude && x.longitude);

  const zipsResp = await frappe.call({ method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_zip_circles" });
  const zipRows = (zipsResp.message || []).filter(z => z.latitude && z.longitude);

  this._drawZipCircles(zipRows);
  await this._drawLeadMarkers(fit);
  this._applyLeadFilters();

  // pull viewport subset after first draw
if (this.$viewportOnly?.is(':checked')) {

  await this._reloadLeadsInView();
}
}

async _reloadLeadsInView(){
  const b = this.map.getBounds();
  if (!b) return;

  const args = {
    north: b.getNorthEast().lat(),
    south: b.getSouthWest().lat(),
    east:  b.getNorthEast().lng(),
    west:  b.getSouthWest().lng(),
    filter_non_red: this.$nonRed?.is(':checked') ? 1 : 0,
    us_only: this.$onlyUS?.is(':checked') ? 1 : 0
  };
  const wf = (this.$wf.val() || '').trim(); if (wf) args.workflow = wf;
  const q  = (this.$q.val()  || '').trim(); if (q)  args.q = q;

  const resp = await frappe.call({
    method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_leads_in_viewport",
    args
  });
  const rows = (resp.message || []).filter(x => x.latitude && x.longitude);

  if (this.$viewportOnly?.is(':checked')) {
    // viewport mode: replace the working set
    this.leads = rows;
  } else {
    // global mode: never shrink; optionally you could merge new rows to ensure freshness
    // For now we just keep allLeads/leads as-is.
    return;
  }

  await this._drawLeadMarkers(false);
  this._applyLeadFilters();
}



  _zoneColor(zone){
    const z = (zone||'').toLowerCase();
    if (z==='green') return '#16a34a';
    if (z==='light green' || z==='light_green' || z==='lightgreen') return '#86efac';
    if (z==='yellow') return '#facc15';
    if (z==='red') return '#ef4444';
    return '#9ca3af';
  }
  _statusColor(wf){
    const s = (wf||'').toLowerCase();
    if (s==='installed') return '#16a34a';
    if (s==='signed')    return '#2563eb';
    if (s==='approved')  return '#22c55e';
    if (s==='submitted') return '#f59e0b';
    if (s==='rejected')  return '#ef4444';
    return '#9ca3af';
  }
// Map your workflow_state -> color/icon
_statusStyle(wf) {
  const s = String(wf || '').trim().toLowerCase();

  // Icon file you saved under: cclms/public/images/navigation_5425952.png
  // In Frappe, public assets from an app are served at /assets/<app-name>/...
  const INSTALLED_ICON = "/assets/cclms/images/navigation_5425952.png";

  // Return an object describing how to render
  // color = used for dot markers and circle/legend
  // iconUrl = used for the custom image pin (Installed)
  switch (s) {
    case "approved":        // Approved => light green
      return { color: "#86efac", iconUrl: null, label: "Approved" };
    case "pending":         // Pending => yellow
      return { color: "#facc15", iconUrl: null, label: "Pending" };
    case "rejected":        // Rejected => red
      return { color: "#ef4444", iconUrl: null, label: "Rejected" };
    case "agreement sent":  // Agreement Sent => green
      return { color: "#16a34a", iconUrl: null, label: "Agreement Sent" };
    case "signed":          // Signed => purple
      return { color: "#7c3aed", iconUrl: null, label: "Signed" };
    case "installed":       // Installed => use your custom icon
      return { color: "#16a34a", iconUrl: INSTALLED_ICON, label: "Installed" };
    default:
      return { color: "#9ca3af", iconUrl: null, label: (wf || "Unknown") };
  }
}

_drawZipCircles(rows){
  this.zipCircles.forEach(c => c.setMap(null));
  this.zipCircles = [];

  if (!this.$toggleZip.is(':checked')) return;

  const allow = new Set(["green","light green","yellow"]); // hide red
  rows.forEach(z => {
    const zc = (z.zone_color || z.zone || '').toLowerCase();
    if (!allow.has(zc)) return;

    const color = this._zoneColor(z.zone_color || z.zone);
    const c = new google.maps.Circle({
      strokeColor: color, strokeOpacity: 1.0, strokeWeight: 2,
      fillColor: color, fillOpacity: 0.22,
      center: { lat: +z.latitude, lng: +z.longitude },
      radius: z.radius_meters ? +z.radius_meters : 8000,
      map: this.map
    });
    const iw = new google.maps.InfoWindow({
      content: `<div style="min-width:200px">
        <b>ZIP ${frappe.utils.escape_html(z.zip_code || '')}</b><br/>
        Zone: <b style="color:${color}">${frappe.utils.escape_html(z.zone_color || z.zone || '')}</b>
      </div>`
    });
    c.addListener('click', (ev) => { iw.setPosition(ev.latLng); iw.open(this.map); });
    this.zipCircles.push(c);
  });
}

async _drawLeadMarkers(fit){
  // Clear existing
  this.leadMarkers.forEach(m => m.setMap && m.setMap(null));
  this.leadMarkers = [];
  this.markerById = {};

  const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
  const sharedInfo = new google.maps.InfoWindow({});

  // A tiny canvas dot (fast) — used when no iconUrl
  const makeDot = (hex) => {
    const s = 16, r = 7;
    const c = document.createElement('canvas');
    c.width = s; c.height = s;
    const ctx = c.getContext('2d');
    ctx.beginPath();
    ctx.arc(s/2, s/2, r, 0, Math.PI*2);
    ctx.fillStyle = hex;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#1f2937';
    ctx.stroke();
    return c;
  };

  let bounds;
  const MAX = 10000; // safety cap
  const rows = this.leads.slice(0, MAX);

  for (const l of rows) {
    const style = this._statusStyle(l.workflow_state);

    let marker;
    if (style.iconUrl) {
      // Your custom image pin for Installed
      marker = new google.maps.Marker({
        position: { lat: +l.latitude, lng: +l.longitude },
        map: this.map,
        icon: {
          url: style.iconUrl,
          scaledSize: new google.maps.Size(28, 28),
          anchor: new google.maps.Point(14, 14)
        },
        title: l.business_name || l.name,
        optimized: true
      });
    } else {
      // Fast DOM pin
      const el = makeDot(style.color);
      marker = new AdvancedMarkerElement({
        position: { lat: +l.latitude, lng: +l.longitude },
        map: this.map,
        content: el,
        title: l.business_name || l.name,
      });
    }

    const html = `
      <div style="min-width:240px">
        <b>${frappe.utils.escape_html(l.business_name || l.name)}</b><br/>
        <div>${frappe.utils.escape_html(l.business_type || '')}</div>
        <div>ZIP: ${frappe.utils.escape_html(l.zip || '')}</div>
        <div>Status: <b>${frappe.utils.escape_html(style.label)}</b></div>
        ${l.zone_color ? `<div>Zone: <b style="color:${this._zoneColor(l.zone_color)}">${frappe.utils.escape_html(l.zone_color)}</b></div>` : ``}
        <div style="margin-top:6px;">
          <a class="btn btn-xs btn-default" href="/app/atm-leads/${encodeURIComponent(l.name)}" target="_blank">Open Lead</a>
        </div>
      </div>`;

    const openInfo = () => {
      sharedInfo.setContent(html);
      // google.maps.Marker vs AdvancedMarkerElement
      if (marker instanceof google.maps.Marker) {
        sharedInfo.open({ anchor: marker, map: this.map });
      } else {
        sharedInfo.open({ map: this.map, position: marker.position });
      }
    };

    // events: AdvancedMarker emits 'gmp-click'
    if (marker.addListener) {
      marker.addListener('click', openInfo);
      marker.addListener('gmp-click', openInfo);
    } else {
      // AdvancedMarkerElement
      marker.addListener('gmp-click', openInfo);
    }

    this.leadMarkers.push(marker);
    this.markerById[l.name] = marker;

    const p = (marker.position || marker.positionLatLng || (marker instanceof AdvancedMarkerElement ? marker.position : null));
    if (p) {
      if (!bounds) bounds = new google.maps.LatLngBounds(p, p);
      else bounds.extend(p);
    }
  }

  if (fit && bounds) this.map.fitBounds(bounds, 60);

  frappe.show_alert({ message: `Leads drawn: ${rows.length}`, indicator: 'blue' });
}

_applyLeadFilters(){
  const q  = (this.$q.val() || '').trim().toLowerCase();
  const wf = (this.$wf.val() || '').trim().toLowerCase();

  this.filteredLeads = [];
  for (let i = 0; i < this.leadMarkers.length; i++) {
    const l = this.leads[i];
    const m = this.leadMarkers[i];
    if (!l || !m) continue;

    const hay = `${l.name} ${l.business_name||''} ${l.business_type||''} ${l.zip||''}`.toLowerCase();
    const okQ = !q || hay.includes(q);

    // map status filter using same canonical labels as _statusStyle
    const label = this._statusStyle(l.workflow_state).label.toLowerCase();
    const okW = !wf || label === wf.toLowerCase();

    const vis = okQ && okW;
    if (m.setMap) m.setMap(vis ? this.map : null); else m.map = vis ? this.map : null;
    if (vis) this.filteredLeads.push(l);
  }

  // (Optional) also filter competitors if you want by same q
  const comps = (this.$toggleComp.is(':checked') ? this.compData : []);
  this._renderCardList(this.filteredLeads, comps);
}

  _showHideZipCircles(){
    const show = this.$toggleZip.is(':checked');
    this.zipCircles.forEach(c => c.setMap(show ? this.map : null));
  }

  async _reloadCompetitors(){
    this.comps.forEach(m => m.setMap && m.setMap(null));
    this.comps = [];
    if (!this.$toggleComp.is(':checked')) return;

    const b = this.map.getBounds();
    if (!b) return;
    const resp = await frappe.call({
      method: "cclms.api.map_view.get_competitors_in_viewport",
      args: { north: b.getNorthEast().lat(), south: b.getSouthWest().lat(), east: b.getNorthEast().lng(), west: b.getSouthWest().lng() }
    });
    const rows = resp.message || [];
    rows.forEach(r => {
      if (!r.latitude || !r.longitude) return;
      const m = new google.maps.Marker({
        position: { lat: +r.latitude, lng: +r.longitude },
        map: this.map,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          fillColor: '#8b5cf6', fillOpacity: 0.9,
          strokeColor: '#1f2937', strokeWeight: 1, scale: 4
        },
        title: r.brand || 'Competitor Kiosk'
      });
      const iw = new google.maps.InfoWindow({ content: `<b>${frappe.utils.escape_html(r.brand||'Competitor')}</b><br/>ZIP: ${frappe.utils.escape_html(r.zip_code||'')}` });
      m.addListener('click', () => iw.open({ anchor: m, map: this.map }));
      this.comps.push(m);
    });
    this.compData = rows;
    this._applyLeadFilters();
  }

  _renderCardList(leads, comps){
    const $list = $(this.w).find('#results_list');
    const $meta = $(this.w).find('#results_meta');
    leads = leads || []; comps = comps || [];
    const total = leads.length + comps.length;
    $meta.text(`${total} results (${leads.length} leads, ${comps.length} competitors)`);

    const zoneDot = (z) => {
      const lc = (z||'').toLowerCase();
      const cls = lc==='green' ? 'green' : (lc==='yellow' ? 'yellow' : (lc==='red' ? 'red' : ''));
      return z ? `<span class="pill ${cls}">${z}</span>` : '';
    };

    const leadCards = leads.slice(0, 600).map(l => `
      <div class="card" data-type="lead" data-name="${frappe.utils.escape_html(l.name)}">
        <h4 class="goto" data-goto="${frappe.utils.escape_html(l.name)}">${frappe.utils.escape_html(l.business_name || l.name)}</h4>
        <div class="muted">${frappe.utils.escape_html(l.business_type||'')} • ZIP ${frappe.utils.escape_html(l.zip||'')}</div>
        <div>Status: <b>${frappe.utils.escape_html(l.workflow_state||'')}</b> ${zoneDot(l.zone_color)}</div>
      </div>
    `);

    const compCards = comps.slice(0, 600).map((c, idx) => `
      <div class="card" data-type="comp" data-idx="${idx}">
        <h4>${frappe.utils.escape_html(c.brand || 'Competitor Kiosk')}</h4>
        <div class="muted">ZIP ${frappe.utils.escape_html(c.zip_code||'')}</div>
      </div>
    `);

    $list.html(leadCards.join('') + compCards.join(''));
    $list.find('[data-type="lead"] .goto').off('click').on('click', (e)=>{
      const name = e.currentTarget.getAttribute('data-goto');
      const m = this.markerById[name];
      if (m) {
        this.map.panTo(m.position);
        this.map.setZoom(Math.max(this.map.getZoom(), 14));
        if (m.__iw) m.__iw.open({ anchor: m, map: this.map });
      }
    });
  }

  async _inspectLocation(latLng){
    const info = await this._lookupPlaceAndAddress(latLng);
    const leadLookup = await this._lookupExistingLead(info, latLng);
    const { address="", zip="", stateCode="", country="", placeName="Nearest Place", placeTypes=[], rating=null, userRatingsTotal=null, placeUrl="", openNow=null } = info || {};
    const bestMatch = leadLookup?.best_match || null;

    const container = document.createElement("div");
    container.style.minWidth = "290px";
    container.innerHTML = `
      <div>
        <b>${frappe.utils.escape_html(placeName)}</b>
        ${placeTypes?.length ? `<div>${frappe.utils.escape_html(placeTypes.join(", "))}</div>` : ""}
        ${rating !== null ? `<div>Rating: <b>${rating.toFixed(1)}</b>${userRatingsTotal ? ` (${userRatingsTotal})` : ""}</div>` : ""}
        ${openNow !== null ? `<div>${openNow ? "Open now" : "Closed now"}</div>` : ""}
        ${address ? `<div>${frappe.utils.escape_html(address)}</div>` : ""}
        ${(zip || stateCode || country) ? `<div>ZIP/Region: ${frappe.utils.escape_html([zip, stateCode, country].filter(Boolean).join(", "))}</div>` : ""}
        ${bestMatch ? `
          <div style="margin-top:8px;padding:8px;border-radius:8px;background:#fef3c7;border:1px solid #f59e0b;">
            <div><b>Already exists</b></div>
            <div>${frappe.utils.escape_html(bestMatch.business_name || bestMatch.name)}</div>
            <div>Stage: <b>${frappe.utils.escape_html(bestMatch.workflow_state || "Draft")}</b></div>
            ${bestMatch.distance_miles !== undefined ? `<div>Distance: ${frappe.utils.escape_html(String(bestMatch.distance_miles))} mi</div>` : ""}
          </div>
        ` : `
          <div style="margin-top:8px;padding:8px;border-radius:8px;background:#ecfdf5;border:1px solid #10b981;">
            <div><b>No matching ATM Lead found</b></div>
            <div>This location looks available for a new lead.</div>
          </div>
        `}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">
          ${bestMatch ? `<button class="btn btn-xs btn-default" data-action="open-existing">Open Existing Lead</button>` : `<button class="btn btn-xs btn-primary" data-action="create-lead">Create ATM Lead</button>`}
          <button class="btn btn-xs btn-default" data-action="create-lead">Open Prefilled Lead</button>
          ${placeUrl ? `<a class="btn btn-xs btn-default" href="${placeUrl}" target="_blank">View in Google Maps</a>` : ""}
        </div>
      </div>
    `;

    container.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.getAttribute("data-action");
        if (action === "open-existing" && bestMatch?.name) {
          window.open(`/app/atm-leads/${encodeURIComponent(bestMatch.name)}`, "_blank");
          return;
        }
        this._openLeadFromMap(info, latLng);
      });
    });

    new google.maps.InfoWindow({ content: container }).open({ map: this.map, position: latLng });
  }

  async _lookupExistingLead(info, latLng){
    try {
      const response = await frappe.call({
        method: "cclms.api.atm_lead_helper.lookup_existing_lead",
        args: {
          address: info?.address || "",
          zip_code: info?.zip || "",
          business_name: info?.placeName || "",
          latitude: latLng?.lat?.(),
          longitude: latLng?.lng?.(),
        },
      });
      return response.message || {};
    } catch (error) {
      console.error("Lead lookup failed", error);
      return {};
    }
  }

  _openLeadFromMap(info, latLng){
    frappe.route_options = {
      business_name: info?.placeName || "",
      address: info?._streetAddress || info?.address || "",
      full_address: info?.address || "",
      city: info?.city || "",
      state: info?.stateName || info?.stateCode || "",
      state_code: info?.stateCode || "",
      zip_code: info?.zip || "",
      country: info?.country || "",
      latitude: latLng?.lat?.(),
      longitude: latLng?.lng?.(),
      google_maps_url: info?.placeUrl || "",
      google_place_types: (info?.placeTypes || []).join(", "),
      google_rating: info?.rating ?? "",
    };
    frappe.new_doc("ATM Leads");
  }

  // reverse geocode + nearest place
  async _lookupPlaceAndAddress(latLng){
    const geocoder = new google.maps.Geocoder();
    const gc = await geocoder.geocode({ location: latLng }).catch(() => null);
    let address="", zip="", stateCode="", stateName="", country="", city="", streetAddress="";
    if (gc?.results?.[0]) {
      address = gc.results[0].formatted_address || "";
      const ac = gc.results[0].address_components || [];
      const streetNumber = (ac.find((x) => x.types.includes("street_number")) || {}).long_name || "";
      const route = (ac.find((x) => x.types.includes("route")) || {}).long_name || "";
      streetAddress = [streetNumber, route].filter(Boolean).join(" ").trim();
      zip = (ac.find((x) => x.types.includes("postal_code")) || {}).long_name || "";
      city = (ac.find((x) => x.types.includes("locality")) || {}).long_name
        || (ac.find((x) => x.types.includes("postal_town")) || {}).long_name
        || "";
      stateCode = (ac.find((x) => x.types.includes("administrative_area_level_1")) || {}).short_name || "";
      stateName = (ac.find((x) => x.types.includes("administrative_area_level_1")) || {}).long_name || "";
      country = (ac.find((x) => x.types.includes("country")) || {}).long_name || "";
    }
    const service = new google.maps.places.PlacesService(this.map);
    const nearby  = await new Promise(res => {
      service.nearbySearch({ location: latLng, radius: 60, rankBy: google.maps.places.RankBy.PROMINENCE }, (r, st) => {
        if (st === google.maps.places.PlacesServiceStatus.OK && r && r.length) res(r); else res(null);
      });
    });
    let placeName="", placeTypes=[], rating=null, userRatingsTotal=null, placeUrl="", openNow=null;
    if (nearby && nearby[0]?.place_id) {
      const details = await new Promise(res => {
        service.getDetails({ placeId: nearby[0].place_id, fields: ['url','name','types','rating','user_ratings_total','opening_hours'] },
          (r, st) => res(st === google.maps.places.PlacesServiceStatus.OK ? r : null));
      });
      if (details) {
        placeName        = details.name || '';
        placeTypes       = (details.types || []).slice(0,4);
        rating           = details.rating ?? null;
        userRatingsTotal = details.user_ratings_total ?? null;
        placeUrl         = details.url || '';
        openNow          = details.opening_hours ? details.opening_hours.isOpen() : null;
      }
    }
    return {
      address,
      zip,
      city,
      stateCode,
      stateName,
      country,
      placeName,
      placeTypes,
      rating,
      userRatingsTotal,
      placeUrl,
      openNow,
      _streetAddress: streetAddress,
    };
  }
}

// frappe.provide("cclms.pages.atm_scouting");

// frappe.pages['atm_scouting'].on_page_load = function(wrapper){
//   const page = frappe.ui.make_app_page({ parent: wrapper, title: 'ATM Scouting (Google Maps)', single_column: true });
//   $(frappe.render_template("atm_scouting", {})).appendTo(page.body);
//   cclms.pages.atm_scouting.ctrl = new ATMScoutingGM(wrapper);
// };

// class ATMScoutingGM {
//   constructor(wrapper){
//     this.w = wrapper;
//     this.map = null;
//     this.googleKey = null;
//     this.mapId = null;
//     this.markerById = {};     // name -> lead marker
//     this.compMarkers = [];    // competitor markers
//     this.compData = [];       // competitor rows for listing
//     this.filteredLeads = [];  // after client-side filter
//     this._debouncedReloadInView = this._debounce(() => this._reloadLeadsInView(), 250);// from Google Maps Settings (optional)
//     this.leads = [];       // {name, business_name, business_type, workflow_state, zip, zone, score, latitude, longitude}
//     this.zipCircles = [];  // google.maps.Circle[]
//     this.leadMarkers = []; // google.maps.marker.AdvancedMarkerElement[]
//     this.comps = [];       // competitor markers
//     this._bindUI();
//     this._boot();
//   }
//   _debounce(fn, ms){
//       let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn.apply(this, a), ms); };
//     }

//   _bindUI(){
//     this.$q = $(this.w).find('#q');
//     this.$wf = $(this.w).find('#wf');
//     this.$toggleZip = $(this.w).find('#toggle_zip');
//     this.$toggleComp = $(this.w).find('#toggle_comp');
//     this.$btnRefresh = $(this.w).find('#btn_refresh');
//     this.$btnInstalled = $(this.w).find('#btn_installed');
//     this.$btnSigned = $(this.w).find('#btn_signed');

//   this.$q.on('input', () => {
//   this._applyLeadFilters();      // hide/show immediately
//   this._debouncedReloadInView(); // refresh from server within 250ms
//     });
//     this.$wf.on('change', () => this._applyLeadFilters());
//     this.$toggleZip.on('change', () => this._showHideZipCircles());
//     this.$toggleComp.on('change', () => this._reloadCompetitors());
//     this.$btnRefresh.on('click', () => this._loadAll(true));
//     this.$btnInstalled.on('click', () => { this.$wf.val('Installed'); this._applyLeadFilters(); });
//     this.$btnSigned.on('click', () => { this.$wf.val('Signed'); this._applyLeadFilters(); });
//   }

//   async _boot(){
//     try{
//       const r = await frappe.call({ method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_google_maps_settings" });
//       this.googleKey = r.message?.api_key || null;
//       this.mapId     = r.message?.map_id  || null;

//       if (!this.googleKey) throw new Error("Google Maps API key not configured.");

//       await this._loadGoogle();
//       this._initMap();
//       await this._loadAll(true);

//       // viewport events (competitors)
//       this.map.addListener('idle', () => {
//         if (this.$toggleComp.is(':checked')) this._reloadCompetitors();
//           this._reloadLeadsInView();   // <-- NEW: refresh leads for current viewport
//         });


//     } catch(e){
//       console.error(e);
//       frappe.msgprint({title:"Map init failed", message: String(e)});
//     }
//   }

//   async _loadGoogle(){
//     // load core with your key
//     await new Promise((resolve, reject) => {
//       if (window.google && google.maps) return resolve();
//       const s = document.createElement('script');
//       s.src = `https://maps.googleapis.com/maps/api/js?key=${this.googleKey}&v=weekly&libraries=places,marker`;
//       s.async = true; s.defer = true;
//       s.onload = resolve; s.onerror = () => reject(new Error("Google JS load failed"));
//       document.head.appendChild(s);
//     });
//     // preload importLibrary API (v=weekly gives it)
//     if (!google.maps.importLibrary) throw new Error("importLibrary API unavailable (use v=weekly)");
//   }
// async _reloadLeadsInView(){
//   const b = this.map.getBounds();
//   if (!b) return;
//   const args = {
//     north: b.getNorthEast().lat(),
//     south: b.getSouthWest().lat(),
//     east:  b.getNorthEast().lng(),
//     west:  b.getSouthWest().lng(),
//     filter_non_red: 1,
//   };
//   const wf = (this.$wf.val() || '').trim(); if (wf) args.workflow = wf;
//   const q  = (this.$q.val()  || '').trim(); if (q)  args.q = q;

//   const resp = await frappe.call({
//     method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_leads_in_viewport",
//     args
//   });
//   this.leads = (resp.message || []).filter(x => x.latitude && x.longitude);
//   await this._drawLeadMarkers(false);
//   this._applyLeadFilters(); // will also re-render the card list
// }

//   async _initMap(){
//   const { Map } = await google.maps.importLibrary("maps");

//   // North America bounds (Alaska to Caribbean)
//   const NA_BOUNDS = {
//     north: 83.0,   // high arctic
//     south: 7.0,    // Panama/Caribbean
//     west: -170.0,  // Aleutians
//     east: -52.0    // Newfoundland
//   };

//   this.map = new Map(document.getElementById('gm-map'), {
//     center: { lat: 39.5, lng: -98.35 },       // continental US center
//     zoom: 4.5,
//     minZoom: 3,
//     maxZoom: 17,
//     restriction: { latLngBounds: NA_BOUNDS, strictBounds: true },
//     mapId: this.mapId || undefined,
//     streetViewControl: false,
//     fullscreenControl: true,
//     mapTypeControl: true,
//   });

//   // instead of create-lead, we will inspect the location
//   this.map.addListener('click', (e) => this._inspectLocation(e.latLng));
// }

// async _loadAll(fit=false){
//   // 1) Leads (non-Red ZIPs by default)
//   const leadsResp = await frappe.call({
//     method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_leads_non_red",
//     args: { filter_non_red: 1 } // set 0 if you ever want all ZIPs
//   });
//   this.leads = (leadsResp.message || []).filter(x => x.latitude && x.longitude);

//   // 2) ZIP circles (for zone overlay)
//   const zipsResp = await frappe.call({
//     method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_zip_circles"
//   });
//   const zipRows = (zipsResp.message || []).filter(z => z.latitude && z.longitude);

//   this._drawZipCircles(zipRows);
//   await this._drawLeadMarkers(fit);
//   this._applyLeadFilters();
// }


//   _zoneColor(zone){
//     const z = (zone||'').toLowerCase();
//     if (z==='green') return '#16a34a';
//     if (z==='light green' || z==='light_green' || z==='lightgreen') return '#86efac';
//     if (z==='yellow') return '#facc15';
//     if (z==='red') return '#ef4444';
//     return '#9ca3af';
//   }

//   _statusColor(wf){
//     const s = (wf||'').toLowerCase();
//     if (s==='installed') return '#16a34a';
//     if (s==='signed')    return '#2563eb';
//     if (s==='approved')  return '#22c55e';
//     if (s==='submitted') return '#f59e0b';
//     if (s==='rejected')  return '#ef4444';
//     return '#9ca3af'; // draft/others
//   }

//   _drawZipCircles(rows){
//     // clear old
//     this.zipCircles.forEach(c => c.setMap(null));
//     this.zipCircles = [];

//     const show = this.$toggleZip.is(':checked');
//     if (!show) return;

//     rows.forEach(z => {
//       const color = this._zoneColor(z.zone_color || z.zone);
//       const c = new google.maps.Circle({
//           strokeColor: color,
//           strokeOpacity: 1.0,       // stronger edge
//           strokeWeight: 2,          // thicker
//           fillColor: color,
//           fillOpacity: 0.22,        // slightly stronger fill for screenshots
//           center: { lat: +z.latitude, lng: +z.longitude },
//           radius: z.radius_meters ? +z.radius_meters : 8000,
//           map: this.map
//         });
//       const html = `
//         <div style="min-width:200px">
//           <b>ZIP ${frappe.utils.escape_html(z.zip_code || '')}</b><br/>
//           Zone: <b style="color:${color}">${frappe.utils.escape_html(z.zone_color || z.zone || '')}</b><br/>
//           ${z.population ? `Population: ${z.population}<br/>` : ``}
//           ${z.margin ? `Margin: ${z.margin}<br/>` : ``}
//           ${z.competitor_kiosks !== undefined ? `Competitors: ${z.competitor_kiosks}<br/>` : ``}
//         </div>`;
//       const iw = new google.maps.InfoWindow({ content: html });
//       c.addListener('click', (ev) => { iw.setPosition(ev.latLng); iw.open(this.map); });
//       this.zipCircles.push(c);
//     });
//   }

//   async _drawLeadMarkers(fit){
//     // clear
//     this.leadMarkers.forEach(m => m.map = null);
//     this.leadMarkers = [];
//     this.markerById = {};

//     const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");

//     let bounds;
//     this.leads.forEach(l => {
//       const color = this._statusColor(l.workflow_state);
//       // simple colored dot marker via SVG
//       const svg = {
//         path: "M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2z",
//         fillColor: color, fillOpacity: 0.9, strokeColor: '#1f2937', strokeWeight: 1, scale: 1
//       };
//       // AdvancedMarkerElement requires an element or glyph; we’ll use a styled div
//       const el = document.createElement('div');
//       el.style.width = '16px'; el.style.height = '16px';
//       el.style.borderRadius = '50%';
//       el.style.background = color;
//       el.style.border = '2px solid #1f2937';

//       const marker = new AdvancedMarkerElement({
//         position: { lat: +l.latitude, lng: +l.longitude },
//         map: this.map,
//         title: l.business_name || l.name,
//         content: el
//       });
//       const html = `
//           <div style="min-width:220px">
//             <b>${frappe.utils.escape_html(l.business_name || l.name)}</b><br/>
//              <div>${frappe.utils.escape_html(l.business_type || '')}</div>
//                 <div>ZIP: ${frappe.utils.escape_html(l.zip || '')}</div>
//                   <div>Status: <b>${frappe.utils.escape_html(l.workflow_state || '')}</b></div>
//                     ${l.zone_color ? `<div>Zone: <b style="color:${this._zoneColor(l.zone_color)}">${frappe.utils.escape_html(l.zone_color)}</b></div>` : ``}
//                       <div style="margin-top:6px;">
//                         <a class="btn btn-xs btn-default" href="/app/atm-leads/${encodeURIComponent(l.name)}" target="_blank">Open Lead</a>
//                                       </div>
//                                             </div>`;

//       const iw = new google.maps.InfoWindow({ content: html });
//       marker.addListener('gmp-click', () => iw.open({ anchor: marker, map: this.map }));

//       marker.__iw = iw;
//         marker.__data = l;
//         this.markerById[l.name] = marker;

//       this.leadMarkers.push(marker);

//       const p = marker.position;
//       if (!bounds) { bounds = new google.maps.LatLngBounds(p, p); }
//       else { bounds.extend(p); }
//     });

//     if (fit && bounds) this.map.fitBounds(bounds, 60);
//   }

//   _applyLeadFilters(){
//   const q  = (this.$q.val() || '').trim().toLowerCase();
//   const wf = (this.$wf.val() || '').trim().toLowerCase();

//   this.filteredLeads = [];
//   this.leadMarkers.forEach((m, i) => {
//     const l = this.leads[i];
//     const hay = `${l.name} ${l.business_name||''} ${l.business_type||''} ${l.zip||''}`.toLowerCase();
//     const okQ = !q || hay.includes(q);
//     const okW = !wf || (l.workflow_state||'').toLowerCase() === wf;
//     const vis = okQ && okW;
//     m.map = vis ? this.map : null;
//     if (vis) this.filteredLeads.push(l);
//   });

//   // Also filter competitors (by same q)
//   const qPred = (row) => {
//     if (!q) return true;
//     const hay = `${row.brand||''} ${row.zip_code||''}`.toLowerCase();
//     return hay.includes(q);
//   };
//   const visibleComps = (this.$toggleComp.is(':checked') ? this.compData.filter(qPred) : []);

//   this._renderCardList(this.filteredLeads, visibleComps);
// }


//   _showHideZipCircles(){
//     const show = this.$toggleZip.is(':checked');
//     this.zipCircles.forEach(c => c.setMap(show ? this.map : null));
//   }

//   async _reloadCompetitors(){
//     // clear old
//     this.comps.forEach(m => m.setMap && m.setMap(null));
//     this.comps = [];
//     if (!this.$toggleComp.is(':checked')) return;

//     const b = this.map.getBounds();
//     if (!b) return;
//     const resp = await frappe.call({
//       method: "cclms.api.map_view.get_competitors_in_viewport",
//       args: { north: b.getNorthEast().lat(), south: b.getSouthWest().lat(), east: b.getNorthEast().lng(), west: b.getSouthWest().lng() }
//     });
//     const rows = resp.message || [];
//     rows.forEach(r => {
//       if (!r.latitude || !r.longitude) return;
//       const m = new google.maps.Marker({
//         position: { lat: +r.latitude, lng: +r.longitude },
//         map: this.map,
//         icon: {
//           path: google.maps.SymbolPath.CIRCLE,
//           fillColor: '#8b5cf6', fillOpacity: 0.9,
//           strokeColor: '#1f2937', strokeWeight: 1, scale: 4
//         },
//         title: r.brand || 'Competitor Kiosk'
//       });
//       const iw = new google.maps.InfoWindow({ content: `<b>${frappe.utils.escape_html(r.brand||'Competitor')}</b><br/>ZIP: ${frappe.utils.escape_html(r.zip_code||'')}` });
//       m.addListener('click', () => iw.open({ anchor: m, map: this.map }));
//       this.comps.push(m);
//       this.compData = rows;           // keep for side list filter
//       this._applyLeadFilters();       // re-render list including comps

//     });
//   }
// async _reloadLeadsInView(){
//   const b = this.map.getBounds();
//   if (!b) return;
//   const args = {
//     north: b.getNorthEast().lat(),
//     south: b.getSouthWest().lat(),
//     east:  b.getNorthEast().lng(),
//     west:  b.getSouthWest().lng(),
//     filter_non_red: 1,
//   };
//   const wf = (this.$wf.val() || '').trim(); if (wf) args.workflow = wf;
//   const q  = (this.$q.val()  || '').trim(); if (q)  args.q = q;

//   const resp = await frappe.call({
//     method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_leads_in_viewport",
//     args
//   });
//   this.leads = (resp.message || []).filter(x => x.latitude && x.longitude);
//   await this._drawLeadMarkers(false);
//   this._applyLeadFilters();
// }


// async _inspectLocation(latLng){
//   const info = await this._lookupPlaceAndAddress(latLng);
//   const {
//     address = '', zip = '', state = '', country = '',
//     placeName = 'Nearest Place', placeTypes = [], rating = null, userRatingsTotal = null, placeUrl = '', openNow = null
//   } = info || {};

//   const lines = [];
//   lines.push(`<b>${frappe.utils.escape_html(placeName)}</b>`);
//   if (placeTypes?.length)  lines.push(`<div>${frappe.utils.escape_html(placeTypes.join(', '))}</div>`);
//   if (rating !== null)     lines.push(`<div>Rating: <b>${rating.toFixed(1)}</b>${userRatingsTotal ? ` (${userRatingsTotal})` : ''}</div>`);
//   if (openNow !== null)    lines.push(`<div>${openNow ? 'Open now' : 'Closed now'}</div>`);
//   if (address)             lines.push(`<div>${frappe.utils.escape_html(address)}</div>`);
//   if (zip || state || country) {
//     lines.push(`<div>ZIP/Region: ${frappe.utils.escape_html([zip, state, country].filter(Boolean).join(', '))}</div>`);
//   }
//   if (placeUrl)            lines.push(`<div style="margin-top:6px;"><a class="btn btn-xs btn-default" href="${placeUrl}" target="_blank">View in Google Maps</a></div>`);

//   new google.maps.InfoWindow({ content: `<div style="min-width:260px">${lines.join('')}</div>` })
//     .open({ map: this.map, position: latLng });
// }

// _renderCardList(leads, comps){
//   const $list = $(this.w).find('#results_list');
//   const $meta = $(this.w).find('#results_meta');
//   leads = leads || [];
//   comps = comps || [];

//   const total = leads.length + comps.length;
//   $meta.text(`${total} results (${leads.length} leads, ${comps.length} competitors)`);

//   const zoneDot = (z) => {
//     const lc = (z||'').toLowerCase();
//     const cls = lc==='green' ? 'green' : (lc==='yellow' ? 'yellow' : (lc==='red' ? 'red' : ''));
//     return z ? `<span class="pill ${cls}">${z}</span>` : '';
//   };

//   const leadCards = leads.slice(0, 500).map(l => `
//     <div class="card" data-type="lead" data-name="${frappe.utils.escape_html(l.name)}">
//       <h4 class="goto" data-goto="${frappe.utils.escape_html(l.name)}">${frappe.utils.escape_html(l.business_name || l.name)}</h4>
//       <div class="muted">${frappe.utils.escape_html(l.business_type||'')} • ZIP ${frappe.utils.escape_html(l.zip||'')}</div>
//       <div>Status: <b>${frappe.utils.escape_html(l.workflow_state||'')}</b> ${zoneDot(l.zone_color)}</div>
//     </div>
//   `);

//   const compCards = comps.slice(0, 500).map((c, idx) => `
//     <div class="card" data-type="comp" data-idx="${idx}">
//       <h4>${frappe.utils.escape_html(c.brand || 'Competitor Kiosk')}</h4>
//       <div class="muted">ZIP ${frappe.utils.escape_html(c.zip_code||'')}</div>
//     </div>
//   `);

//   $list.html(leadCards.join('') + compCards.join(''));

//   // click → pan to marker
//   $list.find('[data-type="lead"] .goto').off('click').on('click', (e)=>{
//     const name = e.currentTarget.getAttribute('data-goto');
//     const m = this.markerById[name];
//     if (m) {
//       this.map.panTo(m.position);
//       this.map.setZoom(Math.max(this.map.getZoom(), 14));
//       if (m.__iw) m.__iw.open({ anchor: m, map: this.map });
//     }
//   });
// }

// // helper: reverse geocode + nearby place + place details
// async _lookupPlaceAndAddress(latLng){
//   const geocoder = new google.maps.Geocoder();
//   const gc = await geocoder.geocode({ location: latLng }).catch(() => null);
//   let address = '', zip = '', state = '', country = '';
//   if (gc?.results?.[0]) {
//     address = gc.results[0].formatted_address || '';
//     const ac = gc.results[0].address_components || [];
//     zip     = (ac.find(x => x.types.includes('postal_code')) || {}).long_name || '';
//     state   = (ac.find(x => x.types.includes('administrative_area_level_1')) || {}).short_name || '';
//     country = (ac.find(x => x.types.includes('country')) || {}).long_name || '';
//   }

//   // Nearby search: closest place around the click
//   const service = new google.maps.places.PlacesService(this.map);
//   const nearby  = await new Promise(res => {
//     service.nearbySearch({ location: latLng, radius: 60, rankBy: google.maps.places.RankBy.PROMINENCE }, (r, status) => {
//       if (status === google.maps.places.PlacesServiceStatus.OK && r && r.length) res(r);
//       else res(null);
//     });
//   });

//   let placeName='', placeTypes=[], rating=null, userRatingsTotal=null, placeUrl='', openNow=null;

//   if (nearby && nearby[0]?.place_id) {
//     const details = await new Promise(res => {
//       service.getDetails({
//         placeId: nearby[0].place_id,
//         fields: ['url','name','types','rating','user_ratings_total','opening_hours']
//       }, (r, status) => res(status === google.maps.places.PlacesServiceStatus.OK ? r : null));
//     });
//     if (details) {
//       placeName        = details.name || '';
//       placeTypes       = (details.types || []).slice(0,4); // keep it tidy
//       rating           = details.rating ?? null;
//       userRatingsTotal = details.user_ratings_total ?? null;
//       placeUrl         = details.url || '';
//       openNow          = details.opening_hours ? details.opening_hours.isOpen() : null;
//     }
//   }

//   return { address, zip, state, country, placeName, placeTypes, rating, userRatingsTotal, placeUrl, openNow };
// }


// }

// frappe.provide("cclms.pages.atm_scouting");

// frappe.pages['atm_scouting'].on_page_load = function(wrapper) {
//   const page = frappe.ui.make_app_page({ parent: wrapper, title: 'ATM Scouting', single_column: true });
//   $(frappe.render_template("atm_scouting", {})).appendTo(page.body);
//   cclms.pages.atm_scouting.ctrl = new ATMScoutingCtrl(wrapper);
// };

// class ATMScoutingCtrl {
//   constructor(wrapper){
//     this.w = wrapper;
//     this.map = null;
//     this.layers = { leads: L.layerGroup(), circles: L.layerGroup(), comp: L.layerGroup(), places: L.layerGroup(), pulses: L.layerGroup() };
//     this.data = { leads:[], circles:[], comp:[], places:[] };
//     this.google_key = null;
//     this._bindUI();
//     this._boot();
//   }

//   _bindUI(){
//     this.$search = $(this.w).find('#search_box');
//     this.$wf = $(this.w).find('#wf_filter');
//     this.$zone = $(this.w).find('#zone_filter');
//     this.$toggleCircles = $(this.w).find('#toggle_circles');
//     this.$toggleComp = $(this.w).find('#toggle_comp');
//     this.$togglePlaces = $(this.w).find('#toggle_places');
//     this.$refresh = $(this.w).find('#btn_refresh');
//     this.$locate = $(this.w).find('#btn_locate');

//     this.$search.on('input', () => this._renderLeads());
//     this.$wf.on('change', () => this._renderLeads());
//     this.$zone.on('change', () => this._renderLeads());
//     this.$toggleCircles.on('change', () => this._renderCircles());
//     this.$toggleComp.on('change', () => this._loadCompetitorsInView());
//     this.$togglePlaces.on('change', () => this._loadPlacesInView());
//     this.$refresh.on('click', () => this._loadAll(true));
//     this.$locate.on('click', () => this._locate());
//   }

//   async _boot(){
//     try{
//       await this._loadLeaflet();
//       this._initMap();
//       const keyResp = await frappe.call({ method: "cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_google_maps_key" });
//       this.google_key = keyResp.message?.api_key || null;
//       if (this.google_key) this._loadGooglePlaces(); // autocomplete + reverse geocode
//       await this._loadAll(true);
//       // fetch viewport overlays when map stops moving
//       this.map.on('moveend', () => { if (this.$toggleComp.is(':checked')) this._loadCompetitorsInView();
//                                      if (this.$togglePlaces.is(':checked')) this._loadPlacesInView(); });
//       // create-lead on click
//       this.map.on('click', (e) => this._onMapClick(e.latlng));
//     } catch(e){
//       console.error(e); frappe.msgprint({title:"Init failed", message:String(e)});
//     }
//   }

//   _loadLeaflet(){
//     return new Promise((resolve,reject)=>{
//       if (window.L) return resolve();
//       const css=document.createElement('link'); css.rel='stylesheet'; css.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
//       const js=document.createElement('script'); js.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'; js.defer=true;
//       js.onload=()=>resolve(); js.onerror=()=>reject(new Error("Leaflet failed"));
//       document.head.appendChild(css); document.head.appendChild(js);
//     });
//   }
//   _loadGooglePlaces(){
//     if (window.google && google.maps) return;
//     const s=document.createElement('script');
//     s.src=`https://maps.googleapis.com/maps/api/js?key=${this.google_key}&libraries=places`;
//     s.defer=true; s.async=true; document.head.appendChild(s);
//   }

//   _initMap(){
//     this.map = L.map('atm-leaflet', { zoomControl: true }).setView([37.8,-96], 5);
//     L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom:19, attribution:'&copy; OpenStreetMap' }).addTo(this.map);
//     // layers
//     this.layers.circles.addTo(this.map);
//     this.layers.leads.addTo(this.map);
//     this.layers.pulses.addTo(this.map);
//     // competitors / places are toggled
//   }

//   async _loadAll(fit=false){
//     // Leads (prefer your central API)
//     const leads = (await frappe.call({ method:"cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_leads_for_map" })).message || [];
//     // Circles for zones
//     const circles = (await frappe.call({ method:"cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_zone_circles" })).message || [];
//     this.data.leads = leads.filter(x => x.latitude && x.longitude);
//     this.data.circles = circles.filter(x => x.latitude && x.longitude);
//     this._renderCircles();
//     this._renderLeads(fit);
//   }

//   _zoneColor(zone){ return ({
//     "Green":"#16a34a", "Light Green":"#86efac", "Yellow":"#facc15", "Red":"#ef4444", "Unclassified":"#9ca3af"
//   }[zone||"Unclassified"]); }

//   _renderCircles(){
//     this.layers.circles.clearLayers();
//     if (!this.$toggleCircles.is(':checked')) return;

//     const allow = new Set(["Green","Light Green","Yellow"]);
//     this.data.circles.forEach(z=>{
//       if (!allow.has(z.zone)) return;
//       const color=this._zoneColor(z.zone);
//       const c=L.circle([z.latitude,z.longitude], {
//         radius: z.radius_meters || 8000, color: color, weight:1, opacity:0.9, fillColor:color, fillOpacity:0.18
//       });
//       c.bindPopup(`
//         <div class="popup-title">ZIP ${frappe.utils.escape_html(z.zip_code||'')}</div>
//         <div class="popup-sub">Zone: <b style="color:${color}">${frappe.utils.escape_html(z.zone||'')}</b></div>
//         ${z.population?`<div>Population: ${z.population}</div>`:''}
//         ${z.margin?`<div>Margin: ${z.margin}</div>`:''}
//         ${z.competitor_kiosks!==undefined?`<div>Competitors: ${z.competitor_kiosks}</div>`:''}
//       `);
//       c.addTo(this.layers.circles);

//       // “Lightning waves” pulse at circle center if Green
//       if (z.zone==="Green"){
//         const PulseIcon = L.DivIcon.extend({ options:{ className:'pulse-green' }});
//         const pulse = L.marker([z.latitude,z.longitude], { icon:new PulseIcon({}) });
//         pulse.addTo(this.layers.pulses);
//       }
//     });
//   }

//   _renderLeads(fit=false){
//     const q=(this.$search.val()||'').toLowerCase();
//     const wf=(this.$wf.val()||'').toLowerCase();
//     const zone=(this.$zone.val()||'').toLowerCase();
//     this.layers.leads.clearLayers();
//     this.layers.pulses.clearLayers();

//     let bounds=null;
//     this.data.leads.filter(l=>{
//       const hay=`${l.name} ${l.business_name||''} ${l.business_type||''} ${l.zip||''}`.toLowerCase();
//       const okq=!q || hay.includes(q);
//       const okw=!wf || (l.workflow_state||'').toLowerCase()===wf;
//       const okz=!zone || (l.zone||'').toLowerCase()===zone;
//       return okq && okw && okz;
//     }).forEach(l=>{
//       const color=this._zoneColor(l.zone);
//       const marker=L.circleMarker([l.latitude,l.longitude], { radius:6, fillColor:color, color:'#111', weight:1, fillOpacity:0.9 });
//       marker.bindPopup(`
//         <div class="popup-title">${frappe.utils.escape_html(l.business_name || l.name)}</div>
//         <div class="popup-sub">${frappe.utils.escape_html(l.business_type||'')} • ZIP ${frappe.utils.escape_html(l.zip||'')}</div>
//         <div>Status: ${frappe.utils.escape_html(l.workflow_state||'')}</div>
//         <div>Zone: <b style="color:${color}">${frappe.utils.escape_html(l.zone||'Unclassified')}</b>${(l.score!==undefined)?` • Score: ${l.score}`:''}</div>
//         <div style="margin-top:6px">
//           <a class="btn btn-xs btn-default" href="/app/atm-leads/${encodeURIComponent(l.name)}" target="_blank">Open Lead</a>
//         </div>
//       `);
//       marker.addTo(this.layers.leads);
//       // pulse for green leads
//       if (l.zone==="Green"){
//         const PulseIcon = L.DivIcon.extend({ options:{ className:'pulse-green' }});
//         L.marker([l.latitude,l.longitude], { icon:new PulseIcon({}) }).addTo(this.layers.pulses);
//       }
//       bounds = bounds ? bounds.extend(marker.getLatLng()) : L.latLngBounds(marker.getLatLng(), marker.getLatLng());
//     });

//     if (fit && bounds) this.map.fitBounds(bounds.pad(0.1));
//   }

//   async _loadCompetitorsInView(){
//     this.layers.comp.clearLayers();
//     if (!this.$toggleComp.is(':checked')) return;
//     const b=this.map.getBounds();
//     try{
//       const resp = await frappe.call({
//         method:"cclms.api.map_view.get_competitors_in_viewport",
//         args:{ north:b.getNorth(), south:b.getSouth(), east:b.getEast(), west:b.getWest() }
//       });
//       const rows = resp.message || [];
//       rows.forEach(r=>{
//         if (!r.latitude || !r.longitude) return;
//         const m = L.circleMarker([+r.latitude,+r.longitude], { radius:4, color:'#8b5cf6', fillColor:'#8b5cf6', fillOpacity:0.8 });
//         m.bindPopup(`<div class="popup-title">${frappe.utils.escape_html(r.brand||'Competitor ATM')}</div>
//                      <div class="popup-sub">ZIP ${frappe.utils.escape_html(r.zip||'')}</div>`);
//         m.addTo(this.layers.comp);
//       });
//       this.layers.comp.addTo(this.map);
//     } catch(e){ console.warn("competitors load failed", e); }
//   }

//   async _loadPlacesInView(){
//     this.layers.places.clearLayers();
//     if (!this.$togglePlaces.is(':checked')) return;
//     const b=this.map.getBounds();
//     try{
//       const resp = await frappe.call({
//         method:"cclms.api.map_view.get_places_in_viewport",
//         args:{ north:b.getNorth(), south:b.getSouth(), east:b.getEast(), west:b.getWest() }
//       });
//       const rows = resp.message || [];
//       rows.forEach(r=>{
//         if (!r.latitude || !r.longitude) return;
//         const m = L.circleMarker([+r.latitude,+r.longitude], { radius:4, color:'#0ea5e9', fillColor:'#0ea5e9', fillOpacity:0.85 });
//         m.bindPopup(`<div class="popup-title">${frappe.utils.escape_html(r.name||'Place')}</div>
//                      <div class="popup-sub">${frappe.utils.escape_html(r.business_type||'')}</div>`);
//         m.addTo(this.layers.places);
//       });
//       this.layers.places.addTo(this.map);
//     } catch(e){ console.warn("places load failed", e); }
//   }

//   async _onMapClick(latlng){
//     // If Google key present, reverse geocode
//     let formatted = '', zip='';
//     if (this.google_key){
//       try{
//         const url=`https://maps.googleapis.com/maps/api/geocode/json?latlng=${latlng.lat},${latlng.lng}&key=${this.google_key}`;
//         const data=await fetch(url).then(r=>r.json());
//         formatted = data?.results?.[0]?.formatted_address || '';
//         const ac = data?.results?.[0]?.address_components || [];
//         zip = (ac.find(c=>c.types.includes("postal_code"))||{}).long_name || '';
//       } catch(e){ /* ignore */ }
//     }
//     // quick duplicate (<=50m)
//     const near=this._nearestLead(latlng, 0.05);
//     const msg = near
//       ? `<div class="popup-title">Existing lead nearby</div><div>${frappe.utils.escape_html(near.business_name||near.name)} (${near.workflow_state})</div>`
//       : `<div class="popup-title">Create lead here?</div><div>${frappe.utils.escape_html(formatted||'Dropped point')}</div><div class="popup-sub">ZIP: ${frappe.utils.escape_html(zip||'')}</div>`;
//     frappe.msgprint({
//       title: "Map Action",
//       message: msg,
//       primary_action: {
//         label: near ? "Open Lead" : "Create ATM Lead",
//         action: async () => {
//           frappe.hide_msgprint();
//           if (near) return window.open(`/app/atm-leads/${encodeURIComponent(near.name)}`,'_blank');
//           const r=await frappe.call({
//             method:"cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.create_lead_from_map",
//             args:{ lat:latlng.lat, lng:latlng.lng, formatted_address:formatted, zip:zip }
//           });
//           if (r.message?.name){
//             frappe.show_alert({message:`Lead created: ${r.message.name}`, indicator:'green'});
//             window.open(`/app/atm-leads/${encodeURIComponent(r.message.name)}`,'_blank');
//             this._loadAll();
//           }
//         }
//       }
//     });
//   }

//   _nearestLead(latlng, km){
//     const toRad=d=>d*Math.PI/180, R=6371;
//     let best=null, bestd=1e9;
//     this.data.leads.forEach(l=>{
//       if (!l.latitude||!l.longitude) return;
//       const dLat=toRad(latlng.lat - l.latitude), dLon=toRad(latlng.lng - l.longitude);
//       const a=Math.sin(dLat/2)**2 + Math.cos(toRad(l.latitude))*Math.cos(toRad(latlng.lat))*Math.sin(dLon/2)**2;
//       const d=2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a))*R;
//       if (d<bestd){bestd=d; best=l;}
//     });
//     return (bestd<=km) ? best : null;
//   }

//   _locate(){
//     if (!navigator.geolocation) return;
//     navigator.geolocation.getCurrentPosition(pos=>{
//       const ll=[pos.coords.latitude, pos.coords.longitude];
//       this.map.setView(ll, 13);
//     });
//   }
// }
