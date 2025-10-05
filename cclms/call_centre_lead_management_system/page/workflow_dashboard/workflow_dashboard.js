// Workflow Dashboard — Operator Companies link + Converted logic
frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
  // ===== CONFIG =====
  const DATE_FIELD = "post_date"; // analyze by post_date window
  const SHOW_STATES = ["Submitted","Approved","Rejected","Agreement Sent","Signed","Converted","Installed"]; // still hide Draft
  const COMPANY_LINK_DOCTYPE = "Operator Companies"; // ✅ matches ATM Leads.company options
  const EXECUTIVE_LINK_DOCTYPE = "Sales Agent";

  // ===== PAGE SHELL =====
  const page = frappe.ui.make_app_page({ parent: wrapper, title: "Workflow Analytics", single_column: true });

  page.body.html(`
    <style>
      .wd-panel { padding: 1rem 1rem .5rem; }
      .wd-row { display:flex; flex-wrap:wrap; align-items:end; gap:.75rem; }
      .wd-input, .wd-btn { height: 40px; border-radius: 12px; }
      .wd-btn { display:inline-flex; align-items:center; gap:.5rem; padding:0 .9rem; }
      .wd-grid { display:grid; gap:.75rem; grid-template-columns: repeat(2,minmax(0,1fr)); }
      @media (min-width: 768px){ .wd-grid { grid-template-columns: repeat(4,minmax(0,1fr)); } }
      .wd-card { border-radius:14px; box-shadow: var(--shadow-sm, 0 1px 2px rgba(0,0,0,.06)); padding:1rem; }
      .wd-muted { color:#6b7280; font-size:.8rem; }
      .wd-big { font-size:1.6rem; font-weight:600; }
      .wd-kpi { display:grid; gap:.75rem; grid-template-columns: repeat(3,minmax(0,1fr)); }
      @media (max-width: 700px){ .wd-kpi{ grid-template-columns: repeat(1,minmax(0,1fr)); } }
      .wd-ratio { font-size:.85rem; color:#6b7280; }
      .wd-link{ text-decoration:none }
      .wd-carry { background:#fff7ed; }
      .frappe-control .awesomplete > input.form-control,
      .frappe-control input.input-with-feedback {
        height: 40px !important; border-radius: 12px !important;
      }
      .frappe-control .control-input { min-width: 220px; }
    </style>

    <div class="wd-panel">
      <!-- Filters Row -->
      <div class="wd-row">
        <div>
          <label class="wd-muted">Start</label><br/>
          <input type="date" id="start_date" class="wd-input"/>
        </div>
        <div>
          <label class="wd-muted">End</label><br/>
          <input type="date" id="end_date" class="wd-input"/>
        </div>

        <!-- Operator Companies (Link) -->
        <div>
          <label class="wd-muted">Operator Company</label><br/>
          <div id="company_ctl"></div>
        </div>
        <button id="open_company" class="btn btn-default wd-btn" title="Open Operator Company">Open</button>

        <!-- Executive (Link) -->
        <div>
          <label class="wd-muted">Executive</label><br/>
          <div id="executive_ctl"></div>
        </div>
        <button id="open_exec" class="btn btn-default wd-btn" title="Open Executive">Open</button>

        <button id="apply" class="btn btn-primary wd-btn">Apply</button>
        <button id="reset" class="btn btn-default wd-btn">Reset</button>
        <a class="btn btn-secondary wd-btn wd-link" href="/preport" target="_blank" rel="noopener">Agent Performance (Web)</a>
      </div>

      <!-- State cards -->
      <div class="wd-grid" id="cards"></div>

      <!-- Conversions  -->
      <h3 class="mt-6">Conversions</h3>
      <div id="kpis" class="wd-kpi mt-2">
        <div class="wd-card"><div class="wd-muted">Total Leads</div><div id="kpi_total" class="wd-big">—</div></div>

        <div class="wd-card"><div class="wd-muted">Rejected vs Total</div><div class="wd-big">
          <span id="kpi_rej">—</span> <span class="wd-ratio" id="kpi_rej_pct"></span>
        </div></div>

        <div class="wd-card"><div class="wd-muted">Approved vs Total</div><div class="wd-big">
          <span id="kpi_appr">—</span> <span class="wd-ratio" id="kpi_appr_pct"></span>
        </div></div>

        <div class="wd-card"><div class="wd-muted">Agreement Sent vs Approved</div><div class="wd-big">
          <span id="kpi_agrsent">—</span> <span class="wd-ratio" id="kpi_agrsent_pct"></span>
        </div></div>

        <!-- Signed now = Signed + Converted -->
        <div class="wd-card"><div class="wd-muted">Signed (incl. Converted) vs Total</div><div class="wd-big">
          <span id="kpi_sign_total">—</span> <span class="wd-ratio" id="kpi_sign_total_pct"></span>
        </div></div>
        <div class="wd-card"><div class="wd-muted">Signed (incl. Converted) vs Approved</div><div class="wd-big">
          <span id="kpi_sign_appr">—</span> <span class="wd-ratio" id="kpi_sign_appr_pct"></span>
        </div></div>
        <div class="wd-card"><div class="wd-muted">Signed (incl. Converted) vs Agreement Sent</div><div class="wd-big">
          <span id="kpi_sign_agrsent">—</span> <span class="wd-ratio" id="kpi_sign_agrsent_pct"></span>
        </div></div>

        <!-- Also show Converted separately (count only) -->
        <div class="wd-card"><div class="wd-muted">Converted (count)</div><div class="wd-big">
          <span id="kpi_conv_only">—</span>
        </div></div>
      </div>

      <!-- Monthly cohort analytics -->
      <div class="wd-card" style="margin-top:1rem;">
        <div class="wd-row">
          <div>
            <label class="wd-muted">Month</label><br/>
            <input type="month" id="mp_month" class="wd-input"/>
          </div>
          <button id="mp_apply" class="btn btn-primary wd-btn">Run Monthly Performance</button>
        </div>

        <div class="wd-grid" style="margin-top:.75rem;">
          <div class="wd-card"><div class="wd-muted">Signed in Month</div><div id="mp_signed" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Converted in Month</div><div id="mp_converted" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Signed + Converted</div><div id="mp_signed_plus" class="wd-big">—</div></div>

          <div class="wd-card"><div class="wd-muted">Same-month Signed</div><div id="mp_same" class="wd-big">—</div></div>
          <div class="wd-card wd-carry"><div class="wd-muted">Carry-in Signed</div><div id="mp_carry" class="wd-big">—</div></div>

          <div class="wd-card"><div class="wd-muted">Same-month Converted</div><div id="mp_conv_same" class="wd-big">—</div></div>
          <div class="wd-card wd-carry"><div class="wd-muted">Carry-in Converted</div><div id="mp_conv_carry" class="wd-big">—</div></div>

          <div class="wd-card"><div class="wd-muted">Total Leads </div><div id="mp_total" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Approved in Month</div><div id="mp_appr" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Agreement Sent in Month</div><div id="mp_sent" class="wd-big">—</div></div>

          <div class="wd-card"><div class="wd-muted">Signed / Total</div><div id="mp_s_t" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Converted / Total</div><div id="mp_c_t" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Signed+Converted / Total</div><div id="mp_sc_t" class="wd-big">—</div></div>
        </div>

        <div class="wd-card" style="margin-top:.75rem;">
          <div class="wd-muted">Sign Lag (days from post_date → sign_date for signatures in month)</div>
          <div id="mp_lag" class="wd-big" style="font-size:1rem;line-height:1.6">
            0–7: — | 8–30: — | 31–60: — | 61–90: — | 90+: —
          </div>
        </div>
      </div>

      <!-- Trend -->
      <h3 class="mt-6">Monthly Trend (Signed)</h3>
      <div class="mt-2"><canvas id="trend_chart" height="160"></canvas></div>
    </div>
  `);

  // ===== STATE =====
  const state = {
    chart: null,
    lastSummary: null,
    lastTrend: [],
    lastMonthly: null,
    linkControls: { company: null, executive: null },
  };

  // ===== HELPERS =====
  const iso = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  const firstOfMonth = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-01`;
  const pct = (n,d) => (!d || d<=0) ? "0%" : `${Math.round((Number(n||0)/Number(d))*100)}%`;

  function setDefaults(){
    const s = document.getElementById("start_date"), e = document.getElementById("end_date");
    if (s && !s.value) s.value = firstOfMonth();
    if (e && !e.value) e.value = iso();
    const m = document.getElementById("mp_month");
    if (m && !m.value) m.value = e?.value?.slice(0,7) || `${new Date().getFullYear()}-${String(new Date().getMonth()+1).padStart(2,"0")}`;
  }

  // Link controls
  function makeLinkControls(){
    state.linkControls.company = frappe.ui.form.make_control({
      parent: document.getElementById("company_ctl"),
      only_input: true,
      df: { fieldtype: "Link", options: COMPANY_LINK_DOCTYPE, fieldname: "company", placeholder: "Operator Company" }
    }); state.linkControls.company.make_input();

    state.linkControls.executive = frappe.ui.form.make_control({
      parent: document.getElementById("executive_ctl"),
      only_input: true,
      df: { fieldtype: "Link", options: EXECUTIVE_LINK_DOCTYPE, fieldname: "executive_name", placeholder: "Sales Agent" }
    }); state.linkControls.executive.make_input();

    document.getElementById("open_company").addEventListener("click", () => {
      const v = state.linkControls.company?.get_value(); if (v) frappe.set_route("Form", COMPANY_LINK_DOCTYPE, v);
    });
    document.getElementById("open_exec").addEventListener("click", () => {
      const v = state.linkControls.executive?.get_value(); if (v) frappe.set_route("Form", EXECUTIVE_LINK_DOCTYPE, v);
    });
  }

  const filters = () => ({
    start_date: document.getElementById("start_date")?.value || null,
    end_date: document.getElementById("end_date")?.value || null,
    company: state.linkControls.company?.get_value() || null,
    executive_name: state.linkControls.executive?.get_value() || null,
    date_field: DATE_FIELD,
  });

  async function call(method, args={}){
    try{ const r = await frappe.call({ method, args }); return r?.message; }
    catch(e){
      const rj = e?.xhr?.responseJSON || {};
      const msg = rj.exception || rj.message || "Server error";
      frappe.msgprint({title:"API Error", message:`<b>${frappe.utils.escape_html(method)}</b><br>${msg}`, indicator:"red"});
      console.error("[Workflow Analytics] API error:", method, rj);
      return null;
    }
  }

  // ===== RENDERERS =====
  async function renderCards(){
    const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", filters());
    const el = document.getElementById("cards"); if(!el) return;
    if(!data || !data.summary){ el.innerHTML = `<div class="wd-muted">No data.</div>`; state.lastSummary=null; return; }

    const summary = { ...data.summary }; delete summary.Draft;
    state.lastSummary = summary;

    // render cards (Ordered, then any extra states)
    const ordered = [];
    SHOW_STATES.forEach(s => { if(summary[s]!=null) ordered.push({state:s,total:summary[s]}); });
    Object.keys(summary).forEach(s => { if(!SHOW_STATES.includes(s)) ordered.push({state:s,total:summary[s]}); });

    const total = ordered.reduce((a,b)=>a+(parseInt(b.total,10)||0),0);
    el.innerHTML = ordered.map(r => `
      <div class="wd-card"><div class="wd-muted">${frappe.utils.escape_html(r.state)}</div><div class="wd-big">${r.total}</div></div>
    `).join("") + `
      <div class="wd-card"><div class="wd-muted">Total (No Draft)</div><div class="wd-big">${total}</div></div>`;

    // ===== KPIs (post_date window) =====
    const rej  = summary["Rejected"]||0;
    const appr = summary["Approved"]||0;
    const agr  = summary["Agreement Sent"]||0;
    const sgn  = summary["Signed"]||0;
    const cnv  = summary["Converted"]||0;
    const signedIncl = (sgn||0) + (cnv||0); // treat Converted as Signed for KPIs

    setText("kpi_total", total);

    setText("kpi_rej", rej); setText("kpi_rej_pct", `(${pct(rej,total)})`);
    setText("kpi_appr", appr); setText("kpi_appr_pct", `(${pct(appr,total)})`);
    setText("kpi_agrsent", agr); setText("kpi_agrsent_pct", `(${pct(agr,Math.max(appr,0))})`);

    setText("kpi_sign_total", signedIncl);
    setText("kpi_sign_total_pct", `(${pct(signedIncl,total)})`);
    setText("kpi_sign_appr", signedIncl);
    setText("kpi_sign_appr_pct", `(${pct(signedIncl,Math.max(appr,0))})`);
    setText("kpi_sign_agrsent", signedIncl);
    setText("kpi_sign_agrsent_pct", `(${pct(signedIncl,Math.max(agr,0))})`);

    setText("kpi_conv_only", cnv);
  }

  async function renderTrend(){
    const data = await call("cclms.api.reports.timeline_trends.get_timeline_trends", { ...filters(), state:"Signed", months:6 });
    const canvas = document.getElementById("trend_chart"); if(!canvas) return;

    const points = (data && data.points) || [];
    state.lastTrend = points;

    if(!points.length){ canvas.outerHTML = `<div class="wd-muted">No trend data for current filters.</div>`; return; }

    const labels = points.map(p=>p.bucket), values = points.map(p=>p.total);
    if(window.Chart && canvas.getContext){
      if(state.chart) state.chart.destroy();
      state.chart = new Chart(canvas.getContext("2d"), { type:"line", data:{ labels, datasets:[{ label:"Signed", data: values }] }, options:{ responsive:true, tension:0.3 }});
    } else if(window.frappe && frappe.Chart){
      // eslint-disable-next-line no-new
      new frappe.Chart(canvas,{ type:"line", data:{ labels, datasets:[{ name:"Signed", values }] }, height:220 });
    } else {
      canvas.outerHTML = `<div class="wd-muted">Chart library not loaded — cards & KPIs are shown.</div>`;
    }
  }

  async function runMonthlyPerformance(){
    const month = (document.getElementById("mp_month")?.value || "").trim() || (document.getElementById("end_date")?.value || "").slice(0,7);
    const mp = await call("cclms.api.reports.monthly_performance.get_monthly_performance", {
      month,
      company: state.linkControls.company?.get_value() || null,
      executive_name: state.linkControls.executive?.get_value() || null
    });
    state.lastMonthly = mp;
    if(!mp) return;

    const c = mp.counts, r = mp.ratios, L = mp.lag_buckets || {};
    setText("mp_signed", c.signed_in_month);
    setText("mp_converted", c.converted_in_month);
    setText("mp_signed_plus", c.signed_plus_converted_in_month);

    setText("mp_same", c.signed_same_month);
    setText("mp_carry", c.signed_carry_in);
    setText("mp_conv_same", c.converted_same_month);
    setText("mp_conv_carry", c.converted_carry_in);

    setText("mp_total", c.total_created);
    setText("mp_appr", c.approved_in_month);
    setText("mp_sent", c.agreement_sent_in_month);

    const fmt = (x)=> x!=null ? `${x}%` : "—";
    setText("mp_s_t", fmt(r.sign_vs_total_pct));
    setText("mp_c_t", fmt(r.converted_vs_total_pct));
    setText("mp_sc_t", fmt(r.signed_plus_converted_vs_total_pct));

    document.getElementById("mp_lag").innerHTML =
      `0–7: <b>${L.d0_7||0}</b> &nbsp;|&nbsp; 8–30: <b>${L.d8_30||0}</b> &nbsp;|&nbsp; 31–60: <b>${L.d31_60||0}</b> &nbsp;|&nbsp; 61–90: <b>${L.d61_90||0}</b> &nbsp;|&nbsp; 90+: <b>${L.d90p||0}</b>`;
  }

  function setText(id, val){ const el = document.getElementById(id); if(el) el.textContent = (val ?? "—"); }

  // ===== WIRE UP =====
  makeLinkControls();
  setDefaults();

  page.body.on("click","#apply", async()=>{ await renderCards(); await renderTrend(); });
  page.body.on("click","#reset", async()=>{
    state.linkControls.company?.set_value("");
    state.linkControls.executive?.set_value("");
    setDefaults();
    await renderCards(); await renderTrend();
  });
  page.body.on("click","#mp_apply", runMonthlyPerformance);

  // initial run
  (async ()=>{ await renderCards(); await renderTrend(); await runMonthlyPerformance(); })();
};


// // Workflow Dashboard — modern UI + KPI conversions (using post_date)
// frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
//   // -------- CONFIG --------
//   const DATE_FIELD = "post_date"; // <-- analyze by post_date
//   const SHOW_STATES = ["Submitted", "Approved", "Rejected", "Agreement Sent", "Signed", "Installed"]; // no "Draft"

//   // -------- PAGE SHELL --------
//   const page = frappe.ui.make_app_page({
//     parent: wrapper,
//     title: "Workflow Analytics",
//     single_column: true,
//   });

//   page.body.html(`
//     <style>
//       .wd-panel { padding: 1rem 1rem 0.5rem; }
//       .wd-row { display:flex; flex-wrap:wrap; align-items:end; gap:.75rem; }
//       .wd-input, .wd-btn {
//         height: 40px; border-radius: 12px;
//       }
//       .wd-input {
//         border:1px solid var(--border-color, #e5e7eb);
//         padding: 0 .75rem; min-width: 190px;
//       }
//       .wd-btn {
//         display:inline-flex; align-items:center; gap:.5rem;
//         padding: 0 .9rem;
//       }
//       .wd-grid { display:grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap:.75rem; }
//       @media (min-width: 768px){ .wd-grid{ grid-template-columns: repeat(4,minmax(0,1fr)); } }
//       .wd-card { border-radius: 14px; box-shadow: var(--shadow-sm, 0 1px 2px rgba(0,0,0,.06)); padding: 1rem; }
//       .wd-muted { color: var(--text-muted, #6b7280); font-size: .8rem; }
//       .wd-big { font-size: 1.6rem; font-weight: 600; }
//       .wd-kpi { display:grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap:.75rem; }
//       @media (max-width: 700px){ .wd-kpi{ grid-template-columns: repeat(1,minmax(0,1fr)); } }
//       .wd-ratio { font-size:.85rem; color: var(--text-muted, #6b7280); }
//       .wd-link { text-decoration:none }
//     </style>

//     <div id="wd-root" class="wd-panel">
//       <div class="wd-row" id="wd-filters">
//         <div>
//           <label class="wd-muted">Start</label><br/>
//           <input type="date" id="start_date" class="wd-input" />
//         </div>
//         <div>
//           <label class="wd-muted">End</label><br/>
//           <input type="date" id="end_date" class="wd-input" />
//         </div>
//         <div>
//           <label class="wd-muted">Company</label><br/>
//           <input type="text" id="company" class="wd-input" placeholder="Company" />
//         </div>
//         <div>
//           <label class="wd-muted">Executive</label><br/>
//           <input type="text" id="executive_name" class="wd-input" placeholder="Agent name" />
//         </div>
//         <button id="apply" class="btn btn-primary wd-btn">Apply</button>
//         <button id="reset" class="btn btn-default wd-btn">Reset</button>
//         <a class="btn btn-secondary wd-btn wd-link" href="/preport" target="_blank" rel="noopener">Agent Performance (Web)</a>
//       </div>

//       <div class="wd-grid" id="cards"></div>

//       <h3 class="mt-6">Conversions</h3>
//       <div id="kpis" class="wd-kpi mt-2">
//         <div class="wd-card"><div class="wd-muted">Total Leads (by Post Date)</div><div id="kpi_total" class="wd-big">—</div></div>
//         <div class="wd-card"><div class="wd-muted">Rejected vs Total</div><div class="wd-big"><span id="kpi_rej">—</span> <span class="wd-ratio" id="kpi_rej_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Approved vs Total</div><div class="wd-big"><span id="kpi_appr">—</span> <span class="wd-ratio" id="kpi_appr_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Agreement Sent vs Approved</div><div class="wd-big"><span id="kpi_agrsent">—</span> <span class="wd-ratio" id="kpi_agrsent_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Signed vs Total</div><div class="wd-big"><span id="kpi_sign">—</span> <span class="wd-ratio" id="kpi_sign_total_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Signed vs Approved</div><div class="wd-big"><span id="kpi_sign2">—</span> <span class="wd-ratio" id="kpi_sign_appr_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Signed vs Agreement Sent</div><div class="wd-big"><span id="kpi_sign3">—</span> <span class="wd-ratio" id="kpi_sign_agrsent_pct"></span></div></div>
//       </div>

//       <h3 class="mt-6">Monthly Trend (Signed)</h3>
//       <div class="mt-2"><canvas id="trend_chart" height="160"></canvas></div>
//     </div>
//   `);

//   // -------- STATE --------
//   const state = { chart: null, lastSummary: null };

//   // -------- HELPERS --------
//   function todayISO(d = new Date()) {
//     const m = (d.getMonth() + 1).toString().padStart(2, "0");
//     const day = d.getDate().toString().padStart(2, "0");
//     return `${d.getFullYear()}-${m}-${day}`;
//   }
//   function firstOfMonthISO(d = new Date()) {
//     const m = (d.getMonth() + 1).toString().padStart(2, "0");
//     return `${d.getFullYear()}-${m}-01`;
//   }
//   function setDefaultDates() {
//     const $s = document.getElementById("start_date");
//     const $e = document.getElementById("end_date");
//     if ($s && !$s.value) $s.value = firstOfMonthISO();
//     if ($e && !$e.value) $e.value = todayISO();
//   }
//   const v = (id) => (document.getElementById(id)?.value || "").trim() || null;
//   const getFilters = () => ({
//     start_date: v("start_date"),
//     end_date: v("end_date"),
//     company: v("company"),
//     executive_name: v("executive_name"),
//     date_field: DATE_FIELD,
//   });
//   async function call(method, args = {}) {
//     try {
//       const r = await frappe.call({ method, args });
//       return r?.message;
//     } catch (e) {
//       const rj = e?.xhr?.responseJSON || {};
//       const msg = rj.exception || rj.message || "Server error";
//       console.error("[Workflow Dashboard] API error:", method, rj);
//       frappe.msgprint({ title: "API Error", message: `<b>${frappe.utils.escape_html(method)}</b><br>${msg}`, indicator: "red" });
//       return null;
//     }
//   }
//   function pct(num, den) {
//     if (!den || den <= 0) return "0%";
//     return `${Math.round((num / den) * 100)}%`;
//   }

//   // -------- RENDERERS --------
//   async function renderCards() {
//     const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", getFilters());
//     const el = document.getElementById("cards");
//     if (!el) return;

//     if (!data || !data.summary) {
//       el.innerHTML = `<div class="wd-muted">No data.</div>`;
//       return;
//     }

//     // Remove Drafts and order known states
//     const summary = { ...data.summary };
//     delete summary["Draft"];
//     state.lastSummary = summary;

//     const ordered = [];
//     SHOW_STATES.forEach((s) => { if (summary[s] != null) ordered.push({ state: s, total: summary[s] }); });
//     Object.keys(summary).forEach((s) => { if (!SHOW_STATES.includes(s)) ordered.push({ state: s, total: summary[s] }); });

//     const total = ordered.reduce((a, b) => a + (parseInt(b.total, 10) || 0), 0);

//     // Cards
//     el.innerHTML = ordered.map((r) => `
//       <div class="wd-card">
//         <div class="wd-muted">${frappe.utils.escape_html(r.state)}</div>
//         <div class="wd-big">${r.total}</div>
//       </div>
//     `).join("") + `
//       <div class="wd-card">
//         <div class="wd-muted">Total (No Draft)</div>
//         <div class="wd-big">${total}</div>
//       </div>`;

//     // KPIs (by post_date)
//     const rej = summary["Rejected"] || 0;
//     const appr = summary["Approved"] || 0;
//     const agr = summary["Agreement Sent"] || 0;
//     const sign = summary["Signed"] || 0;

//     document.getElementById("kpi_total").textContent = total;
//     document.getElementById("kpi_rej").textContent = rej;
//     document.getElementById("kpi_rej_pct").textContent = `(${pct(rej, total)})`;

//     document.getElementById("kpi_appr").textContent = appr;
//     document.getElementById("kpi_appr_pct").textContent = `(${pct(appr, total)})`;

//     document.getElementById("kpi_agrsent").textContent = agr;
//     document.getElementById("kpi_agrsent_pct").textContent = `(${pct(agr, Math.max(appr, 0))})`;

//     document.getElementById("kpi_sign").textContent = sign;
//     document.getElementById("kpi_sign_total_pct").textContent = `(${pct(sign, total)})`;

//     document.getElementById("kpi_sign2").textContent = sign;
//     document.getElementById("kpi_sign_appr_pct").textContent = `(${pct(sign, Math.max(appr, 0))})`;

//     document.getElementById("kpi_sign3").textContent = sign;
//     document.getElementById("kpi_sign_agrsent_pct").textContent = `(${pct(sign, Math.max(agr, 0))})`;
//   }

//   async function renderTrend() {
//     const args = getFilters();
//     const data = await call("cclms.api.reports.timeline_trends.get_timeline_trends", { ...args, state: "Signed", months: 6 });

//     const canvas = document.getElementById("trend_chart");
//     if (!canvas) return;

//     if (!data || !data.points || !data.points.length) {
//       canvas.outerHTML = `<div class="wd-muted">No trend data for current filters.</div>`;
//       return;
//     }

//     const labels = data.points.map((p) => p.bucket);
//     const values = data.points.map((p) => p.total);

//     if (window.Chart && canvas.getContext) {
//       const ctx = canvas.getContext("2d");
//       if (state.chart) state.chart.destroy();
//       state.chart = new Chart(ctx, {
//         type: "line",
//         data: { labels, datasets: [{ label: "Signed", data: values }] },
//         options: { responsive: true, tension: 0.3 },
//       });
//     } else if (window.frappe && frappe.Chart) {
//       // eslint-disable-next-line no-new
//       new frappe.Chart(canvas, { type: "line", data: { labels, datasets: [{ name: "Signed", values }] }, height: 220 });
//     } else {
//       canvas.outerHTML = `<div class="wd-muted">Chart library not loaded — cards & KPIs are shown.</div>`;
//     }
//   }

//   async function refreshAll() {
//     await renderCards();
//     await renderTrend();
//   }

//   function resetFilters() {
//     document.getElementById("company").value = "";
//     document.getElementById("executive_name").value = "";
//     setDefaultDates();
//     refreshAll();
//   }

//   // -------- WIRE UP --------
//   setDefaultDates();
//   page.body.on("click", "#apply", refreshAll);
//   page.body.on("click", "#reset", resetFilters);
//   refreshAll();
// };
