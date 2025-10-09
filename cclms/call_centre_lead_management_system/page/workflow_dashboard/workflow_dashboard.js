// Workflow Dashboard — all-in-one (snapshot cards + cohort KPIs + executives + Highcharts)
// Requires backend endpoints:
// - cclms.api.reports.workflow_summary.get_workflow_summary
// - cclms.api.reports.conversions_summary.get_conversions_summary
// - cclms.api.reports.executive_overview.get_executive_overview
// - cclms.api.reports.timeline_trends.get_multi_trends
// - cclms.api.reports.state_by_executive.get_state_counts_by_executive
// - cclms.api.reports.monthly_performance.get_monthly_performance

frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
  // ---- CONFIG ----
  const DATE_FIELD = "post_date"; // filters use post_date
  const SHOW_STATES = ["Submitted","Approved","Rejected","Agreement Sent","Signed","Converted","Installed"];
  const COMPANY_LINK_DOCTYPE = "Operator Companies";
  const EXECUTIVE_LINK_DOCTYPE = "Sales Agent";

  // ---- PAGE SHELL ----
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: " Analytics Dashboard",
    single_column: true
  });

  page.body.html(`
    <style>
      .wd-panel{padding:1rem 1rem .5rem;}
      .wd-row{display:flex;flex-wrap:wrap;align-items:end;gap:.75rem;}
      .wd-input,.wd-btn{height:40px;border-radius:12px;}
      .wd-btn{display:inline-flex;align-items:center;gap:.5rem;padding:0 .9rem;}
      .wd-grid{display:grid;gap:.75rem;grid-template-columns:repeat(2,minmax(0,1fr));}
      @media (min-width:768px){.wd-grid{grid-template-columns:repeat(4,minmax(0,1fr));}}
      .wd-card{border-radius:14px;box-shadow:0 1px 2px rgba(0,0,0,.06);padding:1rem;}
      .wd-muted{color:#6b7280;font-size:.8rem;}
      .wd-big{font-size:1.6rem;font-weight:600;}
      .wd-kpi{display:grid;gap:.75rem;grid-template-columns:repeat(3,minmax(0,1fr));}
      @media (max-width:700px){.wd-kpi{grid-template-columns:repeat(1,minmax(0,1fr));}}
      .wd-ratio{font-size:.85rem;color:#6b7280;}
      .wd-carry{background:#fff7ed;}
      .frappe-control .awesomplete>input.form-control,
      .frappe-control input.input-with-feedback{height:40px!important;border-radius:12px!important;}
      .frappe-control .control-input{min-width:220px;}
      .wd-table{width:100%;border-collapse:collapse;}
      .wd-table th,.wd-table td{padding:.5rem;border-bottom:1px solid #eee;text-align:right;}
      .wd-table th:first-child,.wd-table td:first-child{text-align:left;}
      .wd-section-title{margin-top:1.25rem;margin-bottom:.25rem;}
    </style>

    <div class="wd-panel">
      <!-- Filters -->
      <div class="wd-row">
        <div>
          <label class="wd-muted">Start</label><br/>
          <input type="date" id="start_date" class="wd-input"/>
        </div>
        <div>
          <label class="wd-muted">End</label><br/>
          <input type="date" id="end_date" class="wd-input"/>
        </div>

        <div>
          <label class="wd-muted">Operator Company</label><br/>
          <div id="company_ctl"></div>
        </div>
        <button id="open_company" class="btn btn-default wd-btn" title="Open Operator Company">Open</button>

        <div>
          <label class="wd-muted">Executive</label><br/>
          <div id="executive_ctl"></div>
        </div>
        <button id="open_exec" class="btn btn-default wd-btn" title="Open Executive">Open</button>

        <button id="apply" class="btn btn-primary wd-btn">Apply</button>
        <button id="reset" class="btn btn-default wd-btn">Reset</button>
        <a class="btn btn-secondary wd-btn" href="/preport" target="_blank" rel="noopener">Agent Performance (Web)</a>
      </div>

      <!-- Snapshot Cards -->
      <div class="wd-grid" id="cards"></div>

      <!-- Cohort KPIs -->
      <h3 class="wd-section-title">Conversions</h3>
      <div id="kpis" class="wd-kpi mt-2">
        <div class="wd-card"><div class="wd-muted">Total Leads (post_date)</div><div id="kpi_total" class="wd-big">—</div></div>
        <div class="wd-card"><div class="wd-muted">Rejected vs Total</div><div class="wd-big"><span id="kpi_rej">—</span> <span class="wd-ratio" id="kpi_rej_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Approved vs Total</div><div class="wd-big"><span id="kpi_appr">—</span> <span class="wd-ratio" id="kpi_appr_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Agreement Sent vs Approved</div><div class="wd-big"><span id="kpi_agrsent">—</span> <span class="wd-ratio" id="kpi_agrsent_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Signed+Converted vs Total</div><div class="wd-big"><span id="kpi_sign_total">—</span> <span class="wd-ratio" id="kpi_sign_total_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Signed+Converted vs Approved</div><div class="wd-big"><span id="kpi_sign_appr">—</span> <span class="wd-ratio" id="kpi_sign_appr_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Signed+Converted vs Agreement Sent</div><div class="wd-big"><span id="kpi_sign_agrsent">—</span> <span class="wd-ratio" id="kpi_sign_agrsent_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Converted</div><div class="wd-big"><span id="kpi_conv_only">—</span></div></div>
      </div>

      <!-- Executives Table -->
      <h3 class="wd-section-title">Executives (only those with leads in range)</h3>
      <div class="wd-card">
        <div id="exec_table">Loading…</div>
      </div>

      <!-- States by Executive (Highcharts) -->
      <h3 class="wd-section-title">States by Executive</h3>
      <div id="state_exec_chart" class="wd-card"></div>

      <!-- Monthly Trend (Highcharts) -->
      <h3 class="wd-section-title">Monthly Trend</h3>
      <div id="trend_chart_div" class="wd-card"></div>

      <!-- Monthly Performance -->
      <h3 class="wd-section-title">Monthly Performance</h3>
      <div class="wd-card">
        <div class="wd-row">
          <div><label class="wd-muted">Month</label><br/><input type="month" id="mp_month" class="wd-input"/></div>
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
          <div class="wd-card"><div class="wd-muted">Total Created (post_date)</div><div id="mp_total" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Approved in Month</div><div id="mp_appr" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Agreement Sent in Month</div><div id="mp_sent" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Signed / Total</div><div id="mp_s_t" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Converted / Total</div><div id="mp_c_t" class="wd-big">—</div></div>
          <div class="wd-card"><div class="wd-muted">Signed+Converted / Total</div><div id="mp_sc_t" class="wd-big">—</div></div>
        </div>
        <div class="wd-card" style="margin-top:.75rem;">
          <div class="wd-muted">Sign Lag (days from post_date → sign_date for signatures in month)</div>
          <div id="mp_lag" class="wd-big" style="font-size:1rem;line-height:1.6">0–7: — | 8–30: — | 31–60: — | 61–90: — | 90+: —</div>
        </div>
      </div>
    </div>
  `);

  // ---- STATE & HELPERS ----
  const state = { linkControls: { company:null, executive:null } };

  const iso = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  const firstOfMonth = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-01`;
  const pct = (n,d) => (!d || d<=0) ? "0%" : `${Math.round((Number(n||0)/Number(d))*100)}%`;

  function setDefaults(){
    const s = document.getElementById("start_date"), e = document.getElementById("end_date");
    if (s && !s.value) s.value = firstOfMonth();
    if (e && !e.value) e.value = iso();
    const m = document.getElementById("mp_month");
    if (m && !m.value) m.value = (e?.value || iso()).slice(0,7);
  }

  function filters(){
    return {
      start_date: document.getElementById("start_date")?.value || null,
      end_date: document.getElementById("end_date")?.value || null,
      company: state.linkControls.company?.get_value() || null,
      executive_name: state.linkControls.executive?.get_value() || null,
      date_field: DATE_FIELD,
    };
  }

  async function call(method, args={}){
    try {
      const r = await frappe.call({ method, args });
      return r?.message;
    } catch(e){
      const rj = e?.xhr?.responseJSON || {};
      const msg = rj.exception || rj.message || "Server error";
      frappe.msgprint({ title:"API Error", message:`<b>${frappe.utils.escape_html(method)}</b><br>${msg}`, indicator:"red" });
      console.error("[Workflow Analytics] API error:", method, rj);
      return null;
    }
  }

  function makeLinkControls(){
    state.linkControls.company = frappe.ui.form.make_control({
      parent: document.getElementById("company_ctl"),
      only_input: true,
      df: { fieldtype:"Link", options: COMPANY_LINK_DOCTYPE, fieldname:"company", placeholder:"Operator Company" }
    }); state.linkControls.company.make_input();

    state.linkControls.executive = frappe.ui.form.make_control({
      parent: document.getElementById("executive_ctl"),
      only_input: true,
      df: { fieldtype:"Link", options: EXECUTIVE_LINK_DOCTYPE, fieldname:"executive_name", placeholder:"Sales Agent" }
    }); state.linkControls.executive.make_input();

    document.getElementById("open_company").onclick = () => {
      const v = state.linkControls.company?.get_value(); if (v) frappe.set_route("Form", COMPANY_LINK_DOCTYPE, v);
    };
    document.getElementById("open_exec").onclick = () => {
      const v = state.linkControls.executive?.get_value(); if (v) frappe.set_route("Form", EXECUTIVE_LINK_DOCTYPE, v);
    };
  }

  // ---- RENDERERS ----

  // 1) Snapshot Cards (current workflow_state, Draft excluded)
  async function renderCards(){
    const f = filters();
    const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", f);
    const el = document.getElementById("cards"); if(!el) return;

    if(!data || !data.summary){
      el.innerHTML = `<div class="wd-muted">No data.</div>`;
      return;
    }

    const summary = { ...data.summary }; // leave Draft out of cards
    delete summary.Draft;

    const ordered = [];
    SHOW_STATES.forEach(s => { if(summary[s]!=null) ordered.push({state:s,total:summary[s]}); });
    Object.keys(summary).forEach(s => { if(!SHOW_STATES.includes(s)) ordered.push({state:s,total:summary[s]}); });

    el.innerHTML =
      ordered.map(r => `
        <div class="wd-card">
          <div class="wd-muted">${frappe.utils.escape_html(r.state)}</div>
          <div class="wd-big">${r.total}</div>
        </div>
      `).join("") +
      `<div class="wd-card"><div class="wd-muted">Total (No Draft)</div><div class="wd-big">${
        ordered.reduce((a,b)=>a+(parseInt(b.total,10)||0),0)
      }</div></div>`;

    // Cohort KPIs (post_date-based)
    await renderKPIs(f);
  }

  // 2) Cohort KPIs (post_date cohort, event-based)
  async function renderKPIs(f){
    const c = await call("cclms.api.reports.conversions_summary.get_conversions_summary", f);
    if(!c) return;

    setText("kpi_total", c.cohort_total);
    setText("kpi_rej", c.rejected);              setText("kpi_rej_pct", `(${c.ratios.rejected_vs_total_pct}%)`);
    setText("kpi_appr", c.approved);             setText("kpi_appr_pct", `(${c.ratios.approved_vs_total_pct}%)`);
    setText("kpi_agrsent", c.agreement_sent);    setText("kpi_agrsent_pct", `(${c.ratios.agrsent_vs_approved_pct}%)`);
    setText("kpi_sign_total", c.signed_plus_converted);
    setText("kpi_sign_total_pct", `(${c.ratios.signedplus_vs_total_pct}%)`);
    setText("kpi_sign_appr", c.signed_plus_converted);
    setText("kpi_sign_appr_pct", `(${c.ratios.signedplus_vs_approved_pct}%)`);
    setText("kpi_sign_agrsent", c.signed_plus_converted);
    setText("kpi_sign_agrsent_pct", `(${c.ratios.signedplus_vs_agrsent_pct}%)`);
    setText("kpi_conv_only", c.converted);
  }

  // 3) Executives table (only executives having >=1 lead in window)
  async function renderExecutives(){
    const f = filters();
    const data = await call("cclms.api.reports.executive_overview.get_executive_overview", {
      start_date: f.start_date, end_date: f.end_date, company: f.company
    });
    const host = document.getElementById("exec_table"); if(!host) return;
    const rows = (data && data.rows) || [];
    if(!rows.length){
      host.innerHTML = `<div class="wd-muted">No executives with leads in this window.</div>`;
      return;
    }
    host.innerHTML = `
      <div style="overflow:auto;">
        <table class="wd-table">
          <thead>
            <tr>
              <th>Executive</th>
              <th>Total (post)</th>
              <th>Approved</th>
              <th>Agreement Sent</th>
              <th>Signed</th>
              <th>Converted</th>
              <th>Signed+Converted</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(r=>`
              <tr>
                <td style="text-align:left;">${frappe.utils.escape_html(r.executive_name||"-")}</td>
                <td>${r.total_post}</td>
                <td>${r.approved}</td>
                <td>${r.agreement_sent}</td>
                <td>${r.signed}</td>
                <td>${r.converted}</td>
                <td>${r.signed_plus_converted}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  }

  // 4) Ensure Highcharts
  function ensureHighcharts(){
    return new Promise(res=>{
      if(window.Highcharts) return res();
      const s=document.createElement("script");
      s.src="https://code.highcharts.com/highcharts.js";
      s.onload=res;
      document.head.appendChild(s);
    });
  }

  // 5) Highcharts: States by Executive (stacked columns, snapshot)
  async function renderStateByExecutive(){
    await ensureHighcharts();
    const f = filters();
    const data = await call("cclms.api.reports.state_by_executive.get_state_counts_by_executive", f);

    const el = document.getElementById("state_exec_chart"); if(!el) return;
    if(!data || !data.categories || !data.categories.length){
      el.innerHTML = `<div class="wd-muted">No data for current filters.</div>`;
      return;
    }
    Highcharts.chart('state_exec_chart', {
      chart: {
        type: 'column',
        scrollablePlotArea: {
          minWidth: Math.max(900, data.categories.length * 90),
          scrollPositionX: 0
        }
      },
      title: { text: 'States by Executive' },
      xAxis: { categories: data.categories, crosshair: true },
      yAxis: { min: 0, title: { text: 'Leads' } },
      legend: { enabled: true },
      tooltip: { shared: true },
      plotOptions: { column: { stacking: 'normal' } },
      series: data.series
    });
  }

  // 6) Highcharts: Multi-series Monthly Trend (Approved / Sent / Signed / Converted)
  async function renderTrend(){
    await ensureHighcharts();
    const f = filters();
    const data = await call("cclms.api.reports.timeline_trends.get_multi_trends", {
      start_date: f.start_date, end_date: f.end_date, company: f.company, executive_name: f.executive_name
    });
    const el = document.getElementById("trend_chart_div"); if(!el) return;
    if(!data || !data.categories || !data.categories.length){
      el.innerHTML = `<div class="wd-muted">No trend data for current filters.</div>`;
      return;
    }
    Highcharts.chart('trend_chart_div', {
      title: { text: 'Monthly Events' },
      xAxis: { categories: data.categories },
      yAxis: { title: { text: 'Count' } },
      legend: { enabled: true },
      series: data.series
    });
  }

  // 7) Monthly Performance (cohort month analytics)
  async function runMonthlyPerformance(){
    const month = (document.getElementById("mp_month")?.value || "").trim()
      || (document.getElementById("end_date")?.value || "").slice(0,7);
    const mp = await call("cclms.api.reports.monthly_performance.get_monthly_performance", {
      month,
      company: state.linkControls.company?.get_value() || null,
      executive_name: state.linkControls.executive?.get_value() || null
    });
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

  function setText(id, val){
    const el = document.getElementById(id);
    if (el) el.textContent = (val ?? "—");
  }

  // ---- WIRE UP ----
  makeLinkControls();
  setDefaults();

  page.body.on("click","#apply", async()=>{
    await renderCards();
    await renderExecutives();
    await renderStateByExecutive();
    await renderTrend();
  });

  page.body.on("click","#reset", async()=>{
    state.linkControls.company?.set_value("");
    state.linkControls.executive?.set_value("");
    setDefaults();
    await renderCards();
    await renderExecutives();
    await renderStateByExecutive();
    await renderTrend();
  });

  page.body.on("click","#mp_apply", runMonthlyPerformance);

  // Initial load
  (async ()=>{
    await renderCards();
    await renderExecutives();
    await renderStateByExecutive();
    await renderTrend();
    await runMonthlyPerformance();
  })();
};

// frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
//   const DATE_FIELD = "post_date";
//   const SHOW_STATES = ["Submitted","Approved","Rejected","Agreement Sent","Signed","Converted","Installed"];
//   const COMPANY_LINK_DOCTYPE = "Operator Companies";
//   const EXECUTIVE_LINK_DOCTYPE = "Sales Agent";

//   const page = frappe.ui.make_app_page({ parent: wrapper, title: "Workflow Analytics", single_column: true });

//   page.body.html(`
//     <style>
//       .wd-panel{padding:1rem 1rem .5rem;}
//       .wd-row{display:flex;flex-wrap:wrap;align-items:end;gap:.75rem;}
//       .wd-input,.wd-btn{height:40px;border-radius:12px;}
//       .wd-btn{display:inline-flex;align-items:center;gap:.5rem;padding:0 .9rem;}
//       .wd-grid{display:grid;gap:.75rem;grid-template-columns:repeat(2,minmax(0,1fr));}
//       @media (min-width:768px){.wd-grid{grid-template-columns:repeat(4,minmax(0,1fr));}}
//       .wd-card{border-radius:14px;box-shadow:0 1px 2px rgba(0,0,0,.06);padding:1rem;}
//       .wd-muted{color:#6b7280;font-size:.8rem;}
//       .wd-big{font-size:1.6rem;font-weight:600;}
//       .wd-kpi{display:grid;gap:.75rem;grid-template-columns:repeat(3,minmax(0,1fr));}
//       @media (max-width:700px){.wd-kpi{grid-template-columns:repeat(1,minmax(0,1fr));}}
//       .wd-ratio{font-size:.85rem;color:#6b7280;}
//       .wd-carry{background:#fff7ed;}
//       .frappe-control .awesomplete>input.form-control,.frappe-control input.input-with-feedback{height:40px!important;border-radius:12px!important;}
//       .frappe-control .control-input{min-width:220px;}
//       .wd-table{width:100%;border-collapse:collapse;}
//       .wd-table th,.wd-table td{padding:.5rem;border-bottom:1px solid #eee;text-align:right;}
//       .wd-table th:first-child,.wd-table td:first-child{text-align:left;}
//     </style>

//     <div class="wd-panel">
//       <div class="wd-row">
//         <div><label class="wd-muted">Start</label><br/><input type="date" id="start_date" class="wd-input"/></div>
//         <div><label class="wd-muted">End</label><br/><input type="date" id="end_date" class="wd-input"/></div>

//         <div><label class="wd-muted">Operator Company</label><br/><div id="company_ctl"></div></div>
//         <button id="open_company" class="btn btn-default wd-btn" title="Open Operator Company">Open</button>

//         <div><label class="wd-muted">Executive</label><br/><div id="executive_ctl"></div></div>
//         <button id="open_exec" class="btn btn-default wd-btn" title="Open Executive">Open</button>

//         <button id="apply" class="btn btn-primary wd-btn">Apply</button>
//         <button id="reset" class="btn btn-default wd-btn">Reset</button>
//         <a class="btn btn-secondary wd-btn" href="/preport" target="_blank" rel="noopener">Agent Performance (Web)</a>
//       </div>

//       <div class="wd-grid" id="cards"></div>

//       <h3 class="mt-6">Conversions</h3>
//       <div id="kpis" class="wd-kpi mt-2">
//         <div class="wd-card"><div class="wd-muted">Total Leads (post_date)</div><div id="kpi_total" class="wd-big">—</div></div>
//         <div class="wd-card"><div class="wd-muted">Rejected vs Total</div><div class="wd-big"><span id="kpi_rej">—</span> <span class="wd-ratio" id="kpi_rej_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Approved vs Total</div><div class="wd-big"><span id="kpi_appr">—</span> <span class="wd-ratio" id="kpi_appr_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Agreement Sent vs Approved</div><div class="wd-big"><span id="kpi_agrsent">—</span> <span class="wd-ratio" id="kpi_agrsent_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Signed+Converted vs Total</div><div class="wd-big"><span id="kpi_sign_total">—</span> <span class="wd-ratio" id="kpi_sign_total_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Signed+Converted vs Approved</div><div class="wd-big"><span id="kpi_sign_appr">—</span> <span class="wd-ratio" id="kpi_sign_appr_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Signed+Converted vs Agreement Sent</div><div class="wd-big"><span id="kpi_sign_agrsent">—</span> <span class="wd-ratio" id="kpi_sign_agrsent_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Converted</div><div class="wd-big"><span id="kpi_conv_only">—</span></div></div>
//       </div>

//       <h3 class="mt-6">Executives (only those with leads in range)</h3>
//       <div class="wd-card"><div id="exec_table">Loading…</div></div>

//       <h3 class="mt-6">Monthly Trend</h3>
//       <div id="trend_chart_div" class="wd-card"></div>

//       <h3 class="mt-6">Monthly Performance</h3>
//       <div class="wd-card">
//         <div class="wd-row">
//           <div><label class="wd-muted">Month</label><br/><input type="month" id="mp_month" class="wd-input"/></div>
//           <button id="mp_apply" class="btn btn-primary wd-btn">Run Monthly Performance</button>
//         </div>
//         <div class="wd-grid" style="margin-top:.75rem;">
//           <div class="wd-card"><div class="wd-muted">Signed in Month</div><div id="mp_signed" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Converted in Month</div><div id="mp_converted" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Signed + Converted</div><div id="mp_signed_plus" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Same-month Signed</div><div id="mp_same" class="wd-big">—</div></div>
//           <div class="wd-card wd-carry"><div class="wd-muted">Carry-in Signed</div><div id="mp_carry" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Same-month Converted</div><div id="mp_conv_same" class="wd-big">—</div></div>
//           <div class="wd-card wd-carry"><div class="wd-muted">Carry-in Converted</div><div id="mp_conv_carry" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Total Created (post_date)</div><div id="mp_total" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Approved in Month</div><div id="mp_appr" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Agreement Sent in Month</div><div id="mp_sent" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Signed / Total</div><div id="mp_s_t" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Converted / Total</div><div id="mp_c_t" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Signed+Converted / Total</div><div id="mp_sc_t" class="wd-big">—</div></div>
//         </div>
//         <div class="wd-card" style="margin-top:.75rem;">
//           <div class="wd-muted">Sign Lag (days from post_date → sign_date for signatures in month)</div>
//           <div id="mp_lag" class="wd-big" style="font-size:1rem;line-height:1.6">0–7: — | 8–30: — | 31–60: — | 61–90: — | 90+: —</div>
//         </div>
//       </div>
//     </div>
//   `);

//   const state = { chart: null, linkControls: { company:null, executive:null } };
//   const iso = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
//   const firstOfMonth = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-01`;
//   const pct = (n,d) => (!d || d<=0) ? "0%" : `${Math.round((Number(n||0)/Number(d))*100)}%`;

//   function setDefaults(){
//     const s = document.getElementById("start_date"), e = document.getElementById("end_date");
//     if (s && !s.value) s.value = firstOfMonth();
//     if (e && !e.value) e.value = iso();
//     const m = document.getElementById("mp_month");
//     if (m && !m.value) m.value = (e?.value || iso()).slice(0,7);
//   }
//   function filters(){ return {
//     start_date: document.getElementById("start_date")?.value || null,
//     end_date: document.getElementById("end_date")?.value || null,
//     company: state.linkControls.company?.get_value() || null,
//     executive_name: state.linkControls.executive?.get_value() || null,
//     date_field: DATE_FIELD,
//   };}

//   async function call(method, args={}){
//     try{ const r = await frappe.call({ method, args }); return r?.message; }
//     catch(e){
//       const rj = e?.xhr?.responseJSON || {}; const msg = rj.exception || rj.message || "Server error";
//       frappe.msgprint({title:"API Error", message:`<b>${frappe.utils.escape_html(method)}</b><br>${msg}`, indicator:"red"});
//       console.error("[Workflow Analytics] API error:", method, rj); return null;
//     }
//   }

//   function makeLinkControls(){
//     state.linkControls.company = frappe.ui.form.make_control({
//       parent: document.getElementById("company_ctl"), only_input:true,
//       df:{ fieldtype:"Link", options:"Operator Companies", fieldname:"company", placeholder:"Operator Company" }
//     }); state.linkControls.company.make_input();
//     state.linkControls.executive = frappe.ui.form.make_control({
//       parent: document.getElementById("executive_ctl"), only_input:true,
//       df:{ fieldtype:"Link", options:"Sales Agent", fieldname:"executive_name", placeholder:"Sales Agent" }
//     }); state.linkControls.executive.make_input();
//     document.getElementById("open_company").onclick = ()=>{ const v = state.linkControls.company?.get_value(); if(v) frappe.set_route("Form","Operator Companies",v); };
//     document.getElementById("open_exec").onclick    = ()=>{ const v = state.linkControls.executive?.get_value(); if(v) frappe.set_route("Form","Sales Agent",v); };
//   }

//   // ----- Cards (snapshot) + KPIs (cohort) -----
//   async function renderCards(){
//     const f = filters();

//     // 1) Cards snapshot
//     const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", f);
//     const el = document.getElementById("cards"); if(!el) return;
//     if(!data || !data.summary){ el.innerHTML = `<div class="wd-muted">No data.</div>`; }
//     else {
//       const summary = { ...data.summary }; delete summary.Draft;
//       const ordered = []; SHOW_STATES.forEach(s => { if(summary[s]!=null) ordered.push({state:s,total:summary[s]}); });
//       Object.keys(summary).forEach(s => { if(!SHOW_STATES.includes(s)) ordered.push({state:s,total:summary[s]}); });
//       el.innerHTML = ordered.map(r=>`
//         <div class="wd-card"><div class="wd-muted">${frappe.utils.escape_html(r.state)}</div><div class="wd-big">${r.total}</div></div>
//       `).join("") + `
//         <div class="wd-card"><div class="wd-muted">Total (No Draft)</div><div class="wd-big">${ordered.reduce((a,b)=>a+(parseInt(b.total,10)||0),0)}</div></div>`;
//     }

//     // 2) Cohort KPIs (FIXES your mismatch)
//     const c = await call("cclms.api.reports.conversions_summary.get_conversions_summary", f);
//     if(c){
//       setText("kpi_total", c.cohort_total);
//       setText("kpi_rej", c.rejected);              setText("kpi_rej_pct", `(${c.ratios.rejected_vs_total_pct}%)`);
//       setText("kpi_appr", c.approved);             setText("kpi_appr_pct", `(${c.ratios.approved_vs_total_pct}%)`);
//       setText("kpi_agrsent", c.agreement_sent);    setText("kpi_agrsent_pct", `(${c.ratios.agrsent_vs_approved_pct}%)`);
//       setText("kpi_sign_total", c.signed_plus_converted);
//       setText("kpi_sign_total_pct", `(${c.ratios.signedplus_vs_total_pct}%)`);
//       setText("kpi_sign_appr", c.signed_plus_converted);
//       setText("kpi_sign_appr_pct", `(${c.ratios.signedplus_vs_approved_pct}%)`);
//       setText("kpi_sign_agrsent", c.signed_plus_converted);
//       setText("kpi_sign_agrsent_pct", `(${c.ratios.signedplus_vs_agrsent_pct}%)`);
//       setText("kpi_conv_only", c.converted);
//     }
//   }

//   // Executives table
//   async function renderExecutives(){
//     const f = filters();
//     const data = await call("cclms.api.reports.executive_overview.get_executive_overview", {
//       start_date: f.start_date, end_date: f.end_date, company: f.company
//     });
//     const host = document.getElementById("exec_table"); if(!host) return;
//     const rows = (data && data.rows) || [];
//     if(!rows.length){ host.innerHTML = `<div class="wd-muted">No executives with leads in this window.</div>`; return; }
//     host.innerHTML = `
//       <div style="overflow:auto;">
//       <table class="wd-table">
//         <thead>
//           <tr>
//             <th>Executive</th>
//             <th>Total (post)</th>
//             <th>Approved</th>
//             <th>Agreement Sent</th>
//             <th>Signed</th>
//             <th>Converted</th>
//             <th>Signed+Converted</th>
//           </tr>
//         </thead>
//         <tbody>
//           ${rows.map(r=>`
//             <tr>
//               <td style="text-align:left;">${frappe.utils.escape_html(r.executive_name||"-")}</td>
//               <td>${r.total_post}</td>
//               <td>${r.approved}</td>
//               <td>${r.agreement_sent}</td>
//               <td>${r.signed}</td>
//               <td>${r.converted}</td>
//               <td>${r.signed_plus_converted}</td>
//             </tr>`).join("")}
//         </tbody>
//       </table></div>`;
//   }

//   // Highcharts trend (multi-series)
//   function ensureHighcharts(){
//     return new Promise(res=>{
//       if(window.Highcharts) return res();
//       const s=document.createElement("script"); s.src="https://code.highcharts.com/highcharts.js"; s.onload=res; document.head.appendChild(s);
//     });
//   }
//   async function renderTrend(){
//     await ensureHighcharts();
//     const f = filters();
//     const data = await call("cclms.api.reports.timeline_trends.get_multi_trends", {
//       start_date: f.start_date, end_date: f.end_date, company: f.company, executive_name: f.executive_name
//     });
//     const el = document.getElementById("trend_chart_div"); if(!el) return;
//     if(!data || !data.categories || !data.categories.length){
//       el.innerHTML = `<div class="wd-muted">No trend data for current filters.</div>`; return;
//     }
//     Highcharts.chart('trend_chart_div', {
//       title: { text: 'Monthly Events' },
//       xAxis: { categories: data.categories },
//       yAxis: { title: { text: 'Count' } },
//       legend: { enabled: true },
//       series: data.series
//     });
//   }

//   // Monthly performance (already good in your build)
//   async function runMonthlyPerformance(){
//     const month = (document.getElementById("mp_month")?.value || "").trim() || (document.getElementById("end_date")?.value || "").slice(0,7);
//     const mp = await call("cclms.api.reports.monthly_performance.get_monthly_performance", {
//       month, company: state.linkControls.company?.get_value() || null, executive_name: state.linkControls.executive?.get_value() || null
//     });
//     if(!mp) return;
//     const c = mp.counts, r = mp.ratios, L = mp.lag_buckets || {};
//     setText("mp_signed", c.signed_in_month);
//     setText("mp_converted", c.converted_in_month);
//     setText("mp_signed_plus", c.signed_plus_converted_in_month);
//     setText("mp_same", c.signed_same_month);
//     setText("mp_carry", c.signed_carry_in);
//     setText("mp_conv_same", c.converted_same_month);
//     setText("mp_conv_carry", c.converted_carry_in);
//     setText("mp_total", c.total_created);
//     setText("mp_appr", c.approved_in_month);
//     setText("mp_sent", c.agreement_sent_in_month);
//     const fmt = (x)=> x!=null ? `${x}%` : "—";
//     setText("mp_s_t", fmt(r.sign_vs_total_pct));
//     setText("mp_c_t", fmt(r.converted_vs_total_pct));
//     setText("mp_sc_t", fmt(r.signed_plus_converted_vs_total_pct));
//     document.getElementById("mp_lag").innerHTML =
//       `0–7: <b>${L.d0_7||0}</b> &nbsp;|&nbsp; 8–30: <b>${L.d8_30||0}</b> &nbsp;|&nbsp; 31–60: <b>${L.d31_60||0}</b> &nbsp;|&nbsp; 61–90: <b>${L.d61_90||0}</b> &nbsp;|&nbsp; 90+: <b>${L.d90p||0}</b>`;
//   }

//   function setText(id,val){ const el=document.getElementById(id); if(el) el.textContent=(val ?? "—"); }

//   // wire up
//   makeLinkControls(); setDefaults();
//   page.body.on("click","#apply", async()=>{ await renderCards(); await renderExecutives(); await renderTrend(); });
//   page.body.on("click","#reset", async()=>{
//     state.linkControls.company?.set_value(""); state.linkControls.executive?.set_value("");
//     setDefaults(); await renderCards(); await renderExecutives(); await renderTrend();
//   });
//   page.body.on("click","#mp_apply", runMonthlyPerformance);

//   (async()=>{ await renderCards(); await renderExecutives(); await renderTrend(); await runMonthlyPerformance(); })();
// };

// Workflow Dashboard — strict totals by post_date, executives table, Highcharts multi-series
// frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
//   const DATE_FIELD = "post_date";
//   const SHOW_STATES = ["Submitted","Approved","Rejected","Agreement Sent","Signed","Converted","Installed"];
//   const COMPANY_LINK_DOCTYPE = "Operator Companies";
//   const EXECUTIVE_LINK_DOCTYPE = "Sales Agent";

//   const page = frappe.ui.make_app_page({ parent: wrapper, title: "Workflow Analytics", single_column: true });

//   page.body.html(`
//     <style>
//       .wd-panel{padding:1rem 1rem .5rem;}
//       .wd-row{display:flex;flex-wrap:wrap;align-items:end;gap:.75rem;}
//       .wd-input,.wd-btn{height:40px;border-radius:12px;}
//       .wd-btn{display:inline-flex;align-items:center;gap:.5rem;padding:0 .9rem;}
//       .wd-grid{display:grid;gap:.75rem;grid-template-columns:repeat(2,minmax(0,1fr));}
//       @media (min-width:768px){.wd-grid{grid-template-columns:repeat(4,minmax(0,1fr));}}
//       .wd-card{border-radius:14px;box-shadow:0 1px 2px rgba(0,0,0,.06);padding:1rem;}
//       .wd-muted{color:#6b7280;font-size:.8rem;}
//       .wd-big{font-size:1.6rem;font-weight:600;}
//       .wd-kpi{display:grid;gap:.75rem;grid-template-columns:repeat(3,minmax(0,1fr));}
//       @media (max-width:700px){.wd-kpi{grid-template-columns:repeat(1,minmax(0,1fr));}}
//       .wd-ratio{font-size:.85rem;color:#6b7280;}
//       .wd-carry{background:#fff7ed;}
//       .frappe-control .awesomplete>input.form-control,.frappe-control input.input-with-feedback{height:40px!important;border-radius:12px!important;}
//       .frappe-control .control-input{min-width:220px;}
//       .wd-table{width:100%;border-collapse:collapse;}
//       .wd-table th,.wd-table td{padding:.5rem;border-bottom:1px solid #eee;text-align:right;}
//       .wd-table th:first-child,.wd-table td:first-child{text-align:left;}
//     </style>

//     <div class="wd-panel">
//       <div class="wd-row">
//         <div><label class="wd-muted">Start</label><br/><input type="date" id="start_date" class="wd-input"/></div>
//         <div><label class="wd-muted">End</label><br/><input type="date" id="end_date" class="wd-input"/></div>

//         <div><label class="wd-muted">Operator Company</label><br/><div id="company_ctl"></div></div>
//         <button id="open_company" class="btn btn-default wd-btn" title="Open Operator Company">Open</button>

//         <div><label class="wd-muted">Executive</label><br/><div id="executive_ctl"></div></div>
//         <button id="open_exec" class="btn btn-default wd-btn" title="Open Executive">Open</button>

//         <button id="apply" class="btn btn-primary wd-btn">Apply</button>
//         <button id="reset" class="btn btn-default wd-btn">Reset</button>
//         <a class="btn btn-secondary wd-btn" href="/preport" target="_blank" rel="noopener">Agent Performance (Web)</a>
//       </div>

//       <div class="wd-grid" id="cards"></div>

//       <h3 class="mt-6">Conversions </h3>
//       <div id="kpis" class="wd-kpi mt-2">
//         <div class="wd-card"><div class="wd-muted">Total Leads (post_date)</div><div id="kpi_total" class="wd-big">—</div></div>
//         <div class="wd-card"><div class="wd-muted">Rejected vs Total</div><div class="wd-big"><span id="kpi_rej">—</span> <span class="wd-ratio" id="kpi_rej_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Approved vs Total</div><div class="wd-big"><span id="kpi_appr">—</span> <span class="wd-ratio" id="kpi_appr_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Agreement Sent vs Approved</div><div class="wd-big"><span id="kpi_agrsent">—</span> <span class="wd-ratio" id="kpi_agrsent_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Signed+Converted vs Total</div><div class="wd-big"><span id="kpi_sign_total">—</span> <span class="wd-ratio" id="kpi_sign_total_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Signed+Converted vs Approved</div><div class="wd-big"><span id="kpi_sign_appr">—</span> <span class="wd-ratio" id="kpi_sign_appr_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Signed+Converted vs Agreement Sent</div><div class="wd-big"><span id="kpi_sign_agrsent">—</span> <span class="wd-ratio" id="kpi_sign_agrsent_pct"></span></div></div>
//         <div class="wd-card"><div class="wd-muted">Converted</div><div class="wd-big"><span id="kpi_conv_only">—</span></div></div>
//       </div>

//       <h3 class="mt-6">Executives (only those with leads in range)</h3>
//       <div class="wd-card">
//         <div id="exec_table">Loading…</div>
//       </div>

//       <h3 class="mt-6">Monthly Trend</h3>
//       <div id="trend_chart_div" class="wd-card"></div>

//       <h3 class="mt-6">Monthly Performance</h3>
//       <div class="wd-card">
//         <div class="wd-row">
//           <div><label class="wd-muted">Month</label><br/><input type="month" id="mp_month" class="wd-input"/></div>
//           <button id="mp_apply" class="btn btn-primary wd-btn">Run Monthly Performance</button>
//         </div>
//         <div class="wd-grid" style="margin-top:.75rem;">
//           <div class="wd-card"><div class="wd-muted">Signed in Month</div><div id="mp_signed" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Converted in Month</div><div id="mp_converted" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Signed + Converted</div><div id="mp_signed_plus" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Same-month Signed</div><div id="mp_same" class="wd-big">—</div></div>
//           <div class="wd-card wd-carry"><div class="wd-muted">Carry-in Signed</div><div id="mp_carry" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Same-month Converted</div><div id="mp_conv_same" class="wd-big">—</div></div>
//           <div class="wd-card wd-carry"><div class="wd-muted">Carry-in Converted</div><div id="mp_conv_carry" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Total Created (post_date)</div><div id="mp_total" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Approved in Month</div><div id="mp_appr" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Agreement Sent in Month</div><div id="mp_sent" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Signed / Total</div><div id="mp_s_t" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Converted / Total</div><div id="mp_c_t" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Signed+Converted / Total</div><div id="mp_sc_t" class="wd-big">—</div></div>
//         </div>
//         <div class="wd-card" style="margin-top:.75rem;">
//           <div class="wd-muted">Sign Lag (days from post_date → sign_date for signatures in month)</div>
//           <div id="mp_lag" class="wd-big" style="font-size:1rem;line-height:1.6">0–7: — | 8–30: — | 31–60: — | 61–90: — | 90+: —</div>
//         </div>
//       </div>
//     </div>
//   `);

//   // state
//   const state = { chart: null, linkControls: { company:null, executive:null } };

//   // helpers
//   const iso = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
//   const firstOfMonth = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-01`;
//   const pct = (n,d) => (!d || d<=0) ? "0%" : `${Math.round((Number(n||0)/Number(d))*100)}%`;
//   function setDefaults(){
//     const s = document.getElementById("start_date"), e = document.getElementById("end_date");
//     if (s && !s.value) s.value = firstOfMonth();
//     if (e && !e.value) e.value = iso();
//     const m = document.getElementById("mp_month");
//     if (m && !m.value) m.value = (e?.value || iso()).slice(0,7);
//   }
//   function filters(){ return {
//     start_date: document.getElementById("start_date")?.value || null,
//     end_date: document.getElementById("end_date")?.value || null,
//     company: state.linkControls.company?.get_value() || null,
//     executive_name: state.linkControls.executive?.get_value() || null,
//     date_field: DATE_FIELD,
//   };}

//   async function call(method, args={}){
//     try{ const r = await frappe.call({ method, args }); return r?.message; }
//     catch(e){
//       const rj = e?.xhr?.responseJSON || {}; const msg = rj.exception || rj.message || "Server error";
//       frappe.msgprint({title:"API Error", message:`<b>${frappe.utils.escape_html(method)}</b><br>${msg}`, indicator:"red"});
//       console.error("[Workflow Analytics] API error:", method, rj); return null;
//     }
//   }

//   // Link controls
//   function makeLinkControls(){
//     state.linkControls.company = frappe.ui.form.make_control({
//       parent: document.getElementById("company_ctl"), only_input:true,
//       df:{ fieldtype:"Link", options:"Operator Companies", fieldname:"company", placeholder:"Operator Company" }
//     }); state.linkControls.company.make_input();
//     state.linkControls.executive = frappe.ui.form.make_control({
//       parent: document.getElementById("executive_ctl"), only_input:true,
//       df:{ fieldtype:"Link", options:"Sales Agent", fieldname:"executive_name", placeholder:"Sales Agent" }
//     }); state.linkControls.executive.make_input();
//     document.getElementById("open_company").onclick = ()=>{ const v = state.linkControls.company?.get_value(); if(v) frappe.set_route("Form","Operator Companies",v); };
//     document.getElementById("open_exec").onclick    = ()=>{ const v = state.linkControls.executive?.get_value(); if(v) frappe.set_route("Form","Sales Agent",v); };
//   }

//   // Cards + KPIs
//   async function renderCards(){
//     const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", filters());
//     const el = document.getElementById("cards"); if(!el) return;
//     if(!data || !data.summary){ el.innerHTML = `<div class="wd-muted">No data.</div>`; return; }

//     const summary = { ...data.summary }; delete summary.Draft;

//     // Cards: ordered states + total (sum of states) AND KPI total from total_all
//     const ordered = []; SHOW_STATES.forEach(s => { if(summary[s]!=null) ordered.push({state:s,total:summary[s]}); });
//     Object.keys(summary).forEach(s => { if(!SHOW_STATES.includes(s)) ordered.push({state:s,total:summary[s]}); });

//     const cards_html = ordered.map(r=>`
//       <div class="wd-card"><div class="wd-muted">${frappe.utils.escape_html(r.state)}</div><div class="wd-big">${r.total}</div></div>
//     `).join("");
//     el.innerHTML = cards_html + `
//       <div class="wd-card"><div class="wd-muted">Total (No Draft)</div><div class="wd-big">${ordered.reduce((a,b)=>a+(parseInt(b.total,10)||0),0)}</div></div>`;

//     // KPIs (use total_all for denominator)
//     const total_all = Number(data.total_all||0);
//     const rej = summary["Rejected"]||0, appr = summary["Approved"]||0, agr = summary["Agreement Sent"]||0, sgn = summary["Signed"]||0, cnv = summary["Converted"]||0;
//     const signedIncl = (sgn||0)+(cnv||0);

//     setText("kpi_total", total_all);
//     setText("kpi_rej", rej); setText("kpi_rej_pct", `(${pct(rej,total_all)})`);
//     setText("kpi_appr", appr); setText("kpi_appr_pct", `(${pct(appr,total_all)})`);
//     setText("kpi_agrsent", agr); setText("kpi_agrsent_pct", `(${pct(agr,Math.max(appr,0))})`);
//     setText("kpi_sign_total", signedIncl); setText("kpi_sign_total_pct", `(${pct(signedIncl,total_all)})`);
//     setText("kpi_sign_appr", signedIncl); setText("kpi_sign_appr_pct", `(${pct(signedIncl,Math.max(appr,0))})`);
//     setText("kpi_sign_agrsent", signedIncl); setText("kpi_sign_agrsent_pct", `(${pct(signedIncl,Math.max(agr,0))})`);
//     setText("kpi_conv_only", cnv);
//   }

//   // Executives table (names only if they have leads in window)
//   async function renderExecutives(){
//     const data = await call("cclms.api.reports.executive_overview.get_executive_overview", {
//       start_date: filters().start_date, end_date: filters().end_date,
//       company: filters().company
//     });
//     const host = document.getElementById("exec_table"); if(!host) return;
//     const rows = (data && data.rows) || [];
//     if(!rows.length){ host.innerHTML = `<div class="wd-muted">No executives with leads in this window.</div>`; return; }
//     host.innerHTML = `
//       <div style="overflow:auto;">
//       <table class="wd-table">
//         <thead>
//           <tr>
//             <th>Executive</th>
//             <th>Total (post)</th>
//             <th>Approved</th>
//             <th>Agreement Sent</th>
//             <th>Signed</th>
//             <th>Converted</th>
//             <th>Signed+Converted</th>
//           </tr>
//         </thead>
//         <tbody>
//           ${rows.map(r=>`
//             <tr>
//               <td style="text-align:left;">${frappe.utils.escape_html(r.executive_name||"-")}</td>
//               <td>${r.total_post}</td>
//               <td>${r.approved}</td>
//               <td>${r.agreement_sent}</td>
//               <td>${r.signed}</td>
//               <td>${r.converted}</td>
//               <td>${r.signed_plus_converted}</td>
//             </tr>`).join("")}
//         </tbody>
//       </table></div>`;
//   }

//   // Highcharts trend (multi-series)
//   function ensureHighcharts(){
//     return new Promise(res=>{
//       if(window.Highcharts) return res();
//       const s=document.createElement("script"); s.src="https://code.highcharts.com/highcharts.js"; s.onload=res; document.head.appendChild(s);
//     });
//   }
//   async function renderTrend(){
//     await ensureHighcharts();
//     const args = filters();
//     const data = await call("cclms.api.reports.timeline_trends.get_multi_trends", {
//       start_date: args.start_date, end_date: args.end_date,
//       company: args.company, executive_name: args.executive_name
//     });
//     const el = document.getElementById("trend_chart_div"); if(!el) return;
//     if(!data || !data.categories || !data.categories.length){
//       el.innerHTML = `<div class="wd-muted">No trend data for current filters.</div>`; return;
//     }
//     Highcharts.chart('trend_chart_div', {
//       title: { text: 'Monthly Events' },
//       xAxis: { categories: data.categories },
//       yAxis: { title: { text: 'Count' } },
//       legend: { enabled: true },
//       series: data.series
//     });
//   }

//   // Monthly performance (unchanged from last version but uses new KPIs we already built)
//   async function runMonthlyPerformance(){
//     const month = (document.getElementById("mp_month")?.value || "").trim() || (document.getElementById("end_date")?.value || "").slice(0,7);
//     const mp = await call("cclms.api.reports.monthly_performance.get_monthly_performance", {
//       month, company: state.linkControls.company?.get_value() || null, executive_name: state.linkControls.executive?.get_value() || null
//     });
//     if(!mp) return;
//     const c = mp.counts, r = mp.ratios, L = mp.lag_buckets || {};
//     setText("mp_signed", c.signed_in_month);
//     setText("mp_converted", c.converted_in_month);
//     setText("mp_signed_plus", c.signed_plus_converted_in_month);
//     setText("mp_same", c.signed_same_month);
//     setText("mp_carry", c.signed_carry_in);
//     setText("mp_conv_same", c.converted_same_month);
//     setText("mp_conv_carry", c.converted_carry_in);
//     setText("mp_total", c.total_created);
//     setText("mp_appr", c.approved_in_month);
//     setText("mp_sent", c.agreement_sent_in_month);
//     const fmt = (x)=> x!=null ? `${x}%` : "—";
//     setText("mp_s_t", fmt(r.sign_vs_total_pct));
//     setText("mp_c_t", fmt(r.converted_vs_total_pct));
//     setText("mp_sc_t", fmt(r.signed_plus_converted_vs_total_pct));
//     document.getElementById("mp_lag").innerHTML =
//       `0–7: <b>${L.d0_7||0}</b> &nbsp;|&nbsp; 8–30: <b>${L.d8_30||0}</b> &nbsp;|&nbsp; 31–60: <b>${L.d31_60||0}</b> &nbsp;|&nbsp; 61–90: <b>${L.d61_90||0}</b> &nbsp;|&nbsp; 90+: <b>${L.d90p||0}</b>`;
//   }

//   function setText(id,val){ const el=document.getElementById(id); if(el) el.textContent=(val ?? "—"); }

//   // wire up
//   makeLinkControls(); setDefaults();
//   page.body.on("click","#apply", async()=>{ await renderCards(); await renderExecutives(); await renderTrend(); });
//   page.body.on("click","#reset", async()=>{
//     state.linkControls.company?.set_value(""); state.linkControls.executive?.set_value("");
//     setDefaults(); await renderCards(); await renderExecutives(); await renderTrend();
//   });
//   page.body.on("click","#mp_apply", runMonthlyPerformance);

//   (async()=>{ await renderCards(); await renderExecutives(); await renderTrend(); await runMonthlyPerformance(); })();
// };

// Workflow Dashboard — Operator Companies link + Converted logic
// ##0
// frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
//   // ===== CONFIG =====
//   const DATE_FIELD = "post_date"; // analyze by post_date window
//   const SHOW_STATES = ["Submitted","Approved","Rejected","Agreement Sent","Signed","Converted","Installed"]; // still hide Draft
//   const COMPANY_LINK_DOCTYPE = "Operator Companies"; // ✅ matches ATM Leads.company options
//   const EXECUTIVE_LINK_DOCTYPE = "Sales Agent";

//   // ===== PAGE SHELL =====
//   const page = frappe.ui.make_app_page({ parent: wrapper, title: "Workflow Analytics", single_column: true });

//   page.body.html(`
//     <style>
//       .wd-panel { padding: 1rem 1rem .5rem; }
//       .wd-row { display:flex; flex-wrap:wrap; align-items:end; gap:.75rem; }
//       .wd-input, .wd-btn { height: 40px; border-radius: 12px; }
//       .wd-btn { display:inline-flex; align-items:center; gap:.5rem; padding:0 .9rem; }
//       .wd-grid { display:grid; gap:.75rem; grid-template-columns: repeat(2,minmax(0,1fr)); }
//       @media (min-width: 768px){ .wd-grid { grid-template-columns: repeat(4,minmax(0,1fr)); } }
//       .wd-card { border-radius:14px; box-shadow: var(--shadow-sm, 0 1px 2px rgba(0,0,0,.06)); padding:1rem; }
//       .wd-muted { color:#6b7280; font-size:.8rem; }
//       .wd-big { font-size:1.6rem; font-weight:600; }
//       .wd-kpi { display:grid; gap:.75rem; grid-template-columns: repeat(3,minmax(0,1fr)); }
//       @media (max-width: 700px){ .wd-kpi{ grid-template-columns: repeat(1,minmax(0,1fr)); } }
//       .wd-ratio { font-size:.85rem; color:#6b7280; }
//       .wd-link{ text-decoration:none }
//       .wd-carry { background:#fff7ed; }
//       .frappe-control .awesomplete > input.form-control,
//       .frappe-control input.input-with-feedback {
//         height: 40px !important; border-radius: 12px !important;
//       }
//       .frappe-control .control-input { min-width: 220px; }
//     </style>

//     <div class="wd-panel">
//       <!-- Filters Row -->
//       <div class="wd-row">
//         <div>
//           <label class="wd-muted">Start</label><br/>
//           <input type="date" id="start_date" class="wd-input"/>
//         </div>
//         <div>
//           <label class="wd-muted">End</label><br/>
//           <input type="date" id="end_date" class="wd-input"/>
//         </div>

//         <!-- Operator Companies (Link) -->
//         <div>
//           <label class="wd-muted">Operator Company</label><br/>
//           <div id="company_ctl"></div>
//         </div>
//         <button id="open_company" class="btn btn-default wd-btn" title="Open Operator Company">Open</button>

//         <!-- Executive (Link) -->
//         <div>
//           <label class="wd-muted">Executive</label><br/>
//           <div id="executive_ctl"></div>
//         </div>
//         <button id="open_exec" class="btn btn-default wd-btn" title="Open Executive">Open</button>

//         <button id="apply" class="btn btn-primary wd-btn">Apply</button>
//         <button id="reset" class="btn btn-default wd-btn">Reset</button>
//         <a class="btn btn-secondary wd-btn wd-link" href="/preport" target="_blank" rel="noopener">Agent Performance (Web)</a>
//       </div>

//       <!-- State cards -->
//       <div class="wd-grid" id="cards"></div>

//       <!-- Conversions  -->
//       <h3 class="mt-6">Conversions</h3>
//       <div id="kpis" class="wd-kpi mt-2">
//         <div class="wd-card"><div class="wd-muted">Total Leads</div><div id="kpi_total" class="wd-big">—</div></div>

//         <div class="wd-card"><div class="wd-muted">Rejected vs Total</div><div class="wd-big">
//           <span id="kpi_rej">—</span> <span class="wd-ratio" id="kpi_rej_pct"></span>
//         </div></div>

//         <div class="wd-card"><div class="wd-muted">Approved vs Total</div><div class="wd-big">
//           <span id="kpi_appr">—</span> <span class="wd-ratio" id="kpi_appr_pct"></span>
//         </div></div>

//         <div class="wd-card"><div class="wd-muted">Agreement Sent vs Approved</div><div class="wd-big">
//           <span id="kpi_agrsent">—</span> <span class="wd-ratio" id="kpi_agrsent_pct"></span>
//         </div></div>

//         <!-- Signed now = Signed + Converted -->
//         <div class="wd-card"><div class="wd-muted">Signed (incl. Converted) vs Total</div><div class="wd-big">
//           <span id="kpi_sign_total">—</span> <span class="wd-ratio" id="kpi_sign_total_pct"></span>
//         </div></div>
//         <div class="wd-card"><div class="wd-muted">Signed (incl. Converted) vs Approved</div><div class="wd-big">
//           <span id="kpi_sign_appr">—</span> <span class="wd-ratio" id="kpi_sign_appr_pct"></span>
//         </div></div>
//         <div class="wd-card"><div class="wd-muted">Signed (incl. Converted) vs Agreement Sent</div><div class="wd-big">
//           <span id="kpi_sign_agrsent">—</span> <span class="wd-ratio" id="kpi_sign_agrsent_pct"></span>
//         </div></div>

//         <!-- Also show Converted separately (count only) -->
//         <div class="wd-card"><div class="wd-muted">Converted (count)</div><div class="wd-big">
//           <span id="kpi_conv_only">—</span>
//         </div></div>
//       </div>

//       <!-- Monthly cohort analytics -->
//       <div class="wd-card" style="margin-top:1rem;">
//         <div class="wd-row">
//           <div>
//             <label class="wd-muted">Month</label><br/>
//             <input type="month" id="mp_month" class="wd-input"/>
//           </div>
//           <button id="mp_apply" class="btn btn-primary wd-btn">Run Monthly Performance</button>
//         </div>

//         <div class="wd-grid" style="margin-top:.75rem;">
//           <div class="wd-card"><div class="wd-muted">Signed in Month</div><div id="mp_signed" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Converted in Month</div><div id="mp_converted" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Signed + Converted</div><div id="mp_signed_plus" class="wd-big">—</div></div>

//           <div class="wd-card"><div class="wd-muted">Same-month Signed</div><div id="mp_same" class="wd-big">—</div></div>
//           <div class="wd-card wd-carry"><div class="wd-muted">Carry-in Signed</div><div id="mp_carry" class="wd-big">—</div></div>

//           <div class="wd-card"><div class="wd-muted">Same-month Converted</div><div id="mp_conv_same" class="wd-big">—</div></div>
//           <div class="wd-card wd-carry"><div class="wd-muted">Carry-in Converted</div><div id="mp_conv_carry" class="wd-big">—</div></div>

//           <div class="wd-card"><div class="wd-muted">Total Leads </div><div id="mp_total" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Approved in Month</div><div id="mp_appr" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Agreement Sent in Month</div><div id="mp_sent" class="wd-big">—</div></div>

//           <div class="wd-card"><div class="wd-muted">Signed / Total</div><div id="mp_s_t" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Converted / Total</div><div id="mp_c_t" class="wd-big">—</div></div>
//           <div class="wd-card"><div class="wd-muted">Signed+Converted / Total</div><div id="mp_sc_t" class="wd-big">—</div></div>
//         </div>

//         <div class="wd-card" style="margin-top:.75rem;">
//           <div class="wd-muted">Sign Lag (days from post_date → sign_date for signatures in month)</div>
//           <div id="mp_lag" class="wd-big" style="font-size:1rem;line-height:1.6">
//             0–7: — | 8–30: — | 31–60: — | 61–90: — | 90+: —
//           </div>
//         </div>
//       </div>

//       <!-- Trend -->
//       <h3 class="mt-6">Monthly Trend (Signed)</h3>
//       <div class="mt-2"><canvas id="trend_chart" height="160"></canvas></div>
//     </div>
//   `);

//   // ===== STATE =====
//   const state = {
//     chart: null,
//     lastSummary: null,
//     lastTrend: [],
//     lastMonthly: null,
//     linkControls: { company: null, executive: null },
//   };

//   // ===== HELPERS =====
//   const iso = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
//   const firstOfMonth = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-01`;
//   const pct = (n,d) => (!d || d<=0) ? "0%" : `${Math.round((Number(n||0)/Number(d))*100)}%`;

//   function setDefaults(){
//     const s = document.getElementById("start_date"), e = document.getElementById("end_date");
//     if (s && !s.value) s.value = firstOfMonth();
//     if (e && !e.value) e.value = iso();
//     const m = document.getElementById("mp_month");
//     if (m && !m.value) m.value = e?.value?.slice(0,7) || `${new Date().getFullYear()}-${String(new Date().getMonth()+1).padStart(2,"0")}`;
//   }

//   // Link controls
//   function makeLinkControls(){
//     state.linkControls.company = frappe.ui.form.make_control({
//       parent: document.getElementById("company_ctl"),
//       only_input: true,
//       df: { fieldtype: "Link", options: COMPANY_LINK_DOCTYPE, fieldname: "company", placeholder: "Operator Company" }
//     }); state.linkControls.company.make_input();

//     state.linkControls.executive = frappe.ui.form.make_control({
//       parent: document.getElementById("executive_ctl"),
//       only_input: true,
//       df: { fieldtype: "Link", options: EXECUTIVE_LINK_DOCTYPE, fieldname: "executive_name", placeholder: "Sales Agent" }
//     }); state.linkControls.executive.make_input();

//     document.getElementById("open_company").addEventListener("click", () => {
//       const v = state.linkControls.company?.get_value(); if (v) frappe.set_route("Form", COMPANY_LINK_DOCTYPE, v);
//     });
//     document.getElementById("open_exec").addEventListener("click", () => {
//       const v = state.linkControls.executive?.get_value(); if (v) frappe.set_route("Form", EXECUTIVE_LINK_DOCTYPE, v);
//     });
//   }

//   const filters = () => ({
//     start_date: document.getElementById("start_date")?.value || null,
//     end_date: document.getElementById("end_date")?.value || null,
//     company: state.linkControls.company?.get_value() || null,
//     executive_name: state.linkControls.executive?.get_value() || null,
//     date_field: DATE_FIELD,
//   });

//   async function call(method, args={}){
//     try{ const r = await frappe.call({ method, args }); return r?.message; }
//     catch(e){
//       const rj = e?.xhr?.responseJSON || {};
//       const msg = rj.exception || rj.message || "Server error";
//       frappe.msgprint({title:"API Error", message:`<b>${frappe.utils.escape_html(method)}</b><br>${msg}`, indicator:"red"});
//       console.error("[Workflow Analytics] API error:", method, rj);
//       return null;
//     }
//   }

//   // ===== RENDERERS =====
//   async function renderCards(){
//     const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", filters());
//     const el = document.getElementById("cards"); if(!el) return;
//     if(!data || !data.summary){ el.innerHTML = `<div class="wd-muted">No data.</div>`; state.lastSummary=null; return; }

//     const summary = { ...data.summary }; delete summary.Draft;
//     state.lastSummary = summary;

//     // render cards (Ordered, then any extra states)
//     const ordered = [];
//     SHOW_STATES.forEach(s => { if(summary[s]!=null) ordered.push({state:s,total:summary[s]}); });
//     Object.keys(summary).forEach(s => { if(!SHOW_STATES.includes(s)) ordered.push({state:s,total:summary[s]}); });

//     const total = ordered.reduce((a,b)=>a+(parseInt(b.total,10)||0),0);
//     el.innerHTML = ordered.map(r => `
//       <div class="wd-card"><div class="wd-muted">${frappe.utils.escape_html(r.state)}</div><div class="wd-big">${r.total}</div></div>
//     `).join("") + `
//       <div class="wd-card"><div class="wd-muted">Total (No Draft)</div><div class="wd-big">${total}</div></div>`;

//     // ===== KPIs (post_date window) =====
//     const rej  = summary["Rejected"]||0;
//     const appr = summary["Approved"]||0;
//     const agr  = summary["Agreement Sent"]||0;
//     const sgn  = summary["Signed"]||0;
//     const cnv  = summary["Converted"]||0;
//     const signedIncl = (sgn||0) + (cnv||0); // treat Converted as Signed for KPIs

//     setText("kpi_total", total);

//     setText("kpi_rej", rej); setText("kpi_rej_pct", `(${pct(rej,total)})`);
//     setText("kpi_appr", appr); setText("kpi_appr_pct", `(${pct(appr,total)})`);
//     setText("kpi_agrsent", agr); setText("kpi_agrsent_pct", `(${pct(agr,Math.max(appr,0))})`);

//     setText("kpi_sign_total", signedIncl);
//     setText("kpi_sign_total_pct", `(${pct(signedIncl,total)})`);
//     setText("kpi_sign_appr", signedIncl);
//     setText("kpi_sign_appr_pct", `(${pct(signedIncl,Math.max(appr,0))})`);
//     setText("kpi_sign_agrsent", signedIncl);
//     setText("kpi_sign_agrsent_pct", `(${pct(signedIncl,Math.max(agr,0))})`);

//     setText("kpi_conv_only", cnv);
//   }

//   async function renderTrend(){
//     const data = await call("cclms.api.reports.timeline_trends.get_timeline_trends", { ...filters(), state:"Signed", months:6 });
//     const canvas = document.getElementById("trend_chart"); if(!canvas) return;

//     const points = (data && data.points) || [];
//     state.lastTrend = points;

//     if(!points.length){ canvas.outerHTML = `<div class="wd-muted">No trend data for current filters.</div>`; return; }

//     const labels = points.map(p=>p.bucket), values = points.map(p=>p.total);
//     if(window.Chart && canvas.getContext){
//       if(state.chart) state.chart.destroy();
//       state.chart = new Chart(canvas.getContext("2d"), { type:"line", data:{ labels, datasets:[{ label:"Signed", data: values }] }, options:{ responsive:true, tension:0.3 }});
//     } else if(window.frappe && frappe.Chart){
//       // eslint-disable-next-line no-new
//       new frappe.Chart(canvas,{ type:"line", data:{ labels, datasets:[{ name:"Signed", values }] }, height:220 });
//     } else {
//       canvas.outerHTML = `<div class="wd-muted">Chart library not loaded — cards & KPIs are shown.</div>`;
//     }
//   }

//   async function runMonthlyPerformance(){
//     const month = (document.getElementById("mp_month")?.value || "").trim() || (document.getElementById("end_date")?.value || "").slice(0,7);
//     const mp = await call("cclms.api.reports.monthly_performance.get_monthly_performance", {
//       month,
//       company: state.linkControls.company?.get_value() || null,
//       executive_name: state.linkControls.executive?.get_value() || null
//     });
//     state.lastMonthly = mp;
//     if(!mp) return;

//     const c = mp.counts, r = mp.ratios, L = mp.lag_buckets || {};
//     setText("mp_signed", c.signed_in_month);
//     setText("mp_converted", c.converted_in_month);
//     setText("mp_signed_plus", c.signed_plus_converted_in_month);

//     setText("mp_same", c.signed_same_month);
//     setText("mp_carry", c.signed_carry_in);
//     setText("mp_conv_same", c.converted_same_month);
//     setText("mp_conv_carry", c.converted_carry_in);

//     setText("mp_total", c.total_created);
//     setText("mp_appr", c.approved_in_month);
//     setText("mp_sent", c.agreement_sent_in_month);

//     const fmt = (x)=> x!=null ? `${x}%` : "—";
//     setText("mp_s_t", fmt(r.sign_vs_total_pct));
//     setText("mp_c_t", fmt(r.converted_vs_total_pct));
//     setText("mp_sc_t", fmt(r.signed_plus_converted_vs_total_pct));

//     document.getElementById("mp_lag").innerHTML =
//       `0–7: <b>${L.d0_7||0}</b> &nbsp;|&nbsp; 8–30: <b>${L.d8_30||0}</b> &nbsp;|&nbsp; 31–60: <b>${L.d31_60||0}</b> &nbsp;|&nbsp; 61–90: <b>${L.d61_90||0}</b> &nbsp;|&nbsp; 90+: <b>${L.d90p||0}</b>`;
//   }

//   function setText(id, val){ const el = document.getElementById(id); if(el) el.textContent = (val ?? "—"); }

//   // ===== WIRE UP =====
//   makeLinkControls();
//   setDefaults();

//   page.body.on("click","#apply", async()=>{ await renderCards(); await renderTrend(); });
//   page.body.on("click","#reset", async()=>{
//     state.linkControls.company?.set_value("");
//     state.linkControls.executive?.set_value("");
//     setDefaults();
//     await renderCards(); await renderTrend();
//   });
//   page.body.on("click","#mp_apply", runMonthlyPerformance);

//   // initial run
//   (async ()=>{ await renderCards(); await renderTrend(); await runMonthlyPerformance(); })();
// };

// ### 02
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
