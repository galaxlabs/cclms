// Workflow Dashboard — modern UI + KPI conversions (using post_date)
frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
  // -------- CONFIG --------
  const DATE_FIELD = "post_date"; // <-- analyze by post_date
  const SHOW_STATES = ["Submitted", "Approved", "Rejected", "Agreement Sent", "Signed", "Installed"]; // no "Draft"

  // -------- PAGE SHELL --------
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Workflow Analytics",
    single_column: true,
  });

  page.body.html(`
    <style>
      .wd-panel { padding: 1rem 1rem 0.5rem; }
      .wd-row { display:flex; flex-wrap:wrap; align-items:end; gap:.75rem; }
      .wd-input, .wd-btn {
        height: 40px; border-radius: 12px;
      }
      .wd-input {
        border:1px solid var(--border-color, #e5e7eb);
        padding: 0 .75rem; min-width: 190px;
      }
      .wd-btn {
        display:inline-flex; align-items:center; gap:.5rem;
        padding: 0 .9rem;
      }
      .wd-grid { display:grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap:.75rem; }
      @media (min-width: 768px){ .wd-grid{ grid-template-columns: repeat(4,minmax(0,1fr)); } }
      .wd-card { border-radius: 14px; box-shadow: var(--shadow-sm, 0 1px 2px rgba(0,0,0,.06)); padding: 1rem; }
      .wd-muted { color: var(--text-muted, #6b7280); font-size: .8rem; }
      .wd-big { font-size: 1.6rem; font-weight: 600; }
      .wd-kpi { display:grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap:.75rem; }
      @media (max-width: 700px){ .wd-kpi{ grid-template-columns: repeat(1,minmax(0,1fr)); } }
      .wd-ratio { font-size:.85rem; color: var(--text-muted, #6b7280); }
      .wd-link { text-decoration:none }
    </style>

    <div id="wd-root" class="wd-panel">
      <div class="wd-row" id="wd-filters">
        <div>
          <label class="wd-muted">Start</label><br/>
          <input type="date" id="start_date" class="wd-input" />
        </div>
        <div>
          <label class="wd-muted">End</label><br/>
          <input type="date" id="end_date" class="wd-input" />
        </div>
        <div>
          <label class="wd-muted">Company</label><br/>
          <input type="text" id="company" class="wd-input" placeholder="Company" />
        </div>
        <div>
          <label class="wd-muted">Executive</label><br/>
          <input type="text" id="executive_name" class="wd-input" placeholder="Agent name" />
        </div>
        <button id="apply" class="btn btn-primary wd-btn">Apply</button>
        <button id="reset" class="btn btn-default wd-btn">Reset</button>
        <a class="btn btn-secondary wd-btn wd-link" href="/preport" target="_blank" rel="noopener">Agent Performance (Web)</a>
      </div>

      <div class="wd-grid" id="cards"></div>

      <h3 class="mt-6">Conversions</h3>
      <div id="kpis" class="wd-kpi mt-2">
        <div class="wd-card"><div class="wd-muted">Total Leads (by Post Date)</div><div id="kpi_total" class="wd-big">—</div></div>
        <div class="wd-card"><div class="wd-muted">Rejected vs Total</div><div class="wd-big"><span id="kpi_rej">—</span> <span class="wd-ratio" id="kpi_rej_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Approved vs Total</div><div class="wd-big"><span id="kpi_appr">—</span> <span class="wd-ratio" id="kpi_appr_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Agreement Sent vs Approved</div><div class="wd-big"><span id="kpi_agrsent">—</span> <span class="wd-ratio" id="kpi_agrsent_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Signed vs Total</div><div class="wd-big"><span id="kpi_sign">—</span> <span class="wd-ratio" id="kpi_sign_total_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Signed vs Approved</div><div class="wd-big"><span id="kpi_sign2">—</span> <span class="wd-ratio" id="kpi_sign_appr_pct"></span></div></div>
        <div class="wd-card"><div class="wd-muted">Signed vs Agreement Sent</div><div class="wd-big"><span id="kpi_sign3">—</span> <span class="wd-ratio" id="kpi_sign_agrsent_pct"></span></div></div>
      </div>

      <h3 class="mt-6">Monthly Trend (Signed)</h3>
      <div class="mt-2"><canvas id="trend_chart" height="160"></canvas></div>
    </div>
  `);

  // -------- STATE --------
  const state = { chart: null, lastSummary: null };

  // -------- HELPERS --------
  function todayISO(d = new Date()) {
    const m = (d.getMonth() + 1).toString().padStart(2, "0");
    const day = d.getDate().toString().padStart(2, "0");
    return `${d.getFullYear()}-${m}-${day}`;
  }
  function firstOfMonthISO(d = new Date()) {
    const m = (d.getMonth() + 1).toString().padStart(2, "0");
    return `${d.getFullYear()}-${m}-01`;
  }
  function setDefaultDates() {
    const $s = document.getElementById("start_date");
    const $e = document.getElementById("end_date");
    if ($s && !$s.value) $s.value = firstOfMonthISO();
    if ($e && !$e.value) $e.value = todayISO();
  }
  const v = (id) => (document.getElementById(id)?.value || "").trim() || null;
  const getFilters = () => ({
    start_date: v("start_date"),
    end_date: v("end_date"),
    company: v("company"),
    executive_name: v("executive_name"),
    date_field: DATE_FIELD,
  });
  async function call(method, args = {}) {
    try {
      const r = await frappe.call({ method, args });
      return r?.message;
    } catch (e) {
      const rj = e?.xhr?.responseJSON || {};
      const msg = rj.exception || rj.message || "Server error";
      console.error("[Workflow Dashboard] API error:", method, rj);
      frappe.msgprint({ title: "API Error", message: `<b>${frappe.utils.escape_html(method)}</b><br>${msg}`, indicator: "red" });
      return null;
    }
  }
  function pct(num, den) {
    if (!den || den <= 0) return "0%";
    return `${Math.round((num / den) * 100)}%`;
  }

  // -------- RENDERERS --------
  async function renderCards() {
    const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", getFilters());
    const el = document.getElementById("cards");
    if (!el) return;

    if (!data || !data.summary) {
      el.innerHTML = `<div class="wd-muted">No data.</div>`;
      return;
    }

    // Remove Drafts and order known states
    const summary = { ...data.summary };
    delete summary["Draft"];
    state.lastSummary = summary;

    const ordered = [];
    SHOW_STATES.forEach((s) => { if (summary[s] != null) ordered.push({ state: s, total: summary[s] }); });
    Object.keys(summary).forEach((s) => { if (!SHOW_STATES.includes(s)) ordered.push({ state: s, total: summary[s] }); });

    const total = ordered.reduce((a, b) => a + (parseInt(b.total, 10) || 0), 0);

    // Cards
    el.innerHTML = ordered.map((r) => `
      <div class="wd-card">
        <div class="wd-muted">${frappe.utils.escape_html(r.state)}</div>
        <div class="wd-big">${r.total}</div>
      </div>
    `).join("") + `
      <div class="wd-card">
        <div class="wd-muted">Total (No Draft)</div>
        <div class="wd-big">${total}</div>
      </div>`;

    // KPIs (by post_date)
    const rej = summary["Rejected"] || 0;
    const appr = summary["Approved"] || 0;
    const agr = summary["Agreement Sent"] || 0;
    const sign = summary["Signed"] || 0;

    document.getElementById("kpi_total").textContent = total;
    document.getElementById("kpi_rej").textContent = rej;
    document.getElementById("kpi_rej_pct").textContent = `(${pct(rej, total)})`;

    document.getElementById("kpi_appr").textContent = appr;
    document.getElementById("kpi_appr_pct").textContent = `(${pct(appr, total)})`;

    document.getElementById("kpi_agrsent").textContent = agr;
    document.getElementById("kpi_agrsent_pct").textContent = `(${pct(agr, Math.max(appr, 0))})`;

    document.getElementById("kpi_sign").textContent = sign;
    document.getElementById("kpi_sign_total_pct").textContent = `(${pct(sign, total)})`;

    document.getElementById("kpi_sign2").textContent = sign;
    document.getElementById("kpi_sign_appr_pct").textContent = `(${pct(sign, Math.max(appr, 0))})`;

    document.getElementById("kpi_sign3").textContent = sign;
    document.getElementById("kpi_sign_agrsent_pct").textContent = `(${pct(sign, Math.max(agr, 0))})`;
  }

  async function renderTrend() {
    const args = getFilters();
    const data = await call("cclms.api.reports.timeline_trends.get_timeline_trends", { ...args, state: "Signed", months: 6 });

    const canvas = document.getElementById("trend_chart");
    if (!canvas) return;

    if (!data || !data.points || !data.points.length) {
      canvas.outerHTML = `<div class="wd-muted">No trend data for current filters.</div>`;
      return;
    }

    const labels = data.points.map((p) => p.bucket);
    const values = data.points.map((p) => p.total);

    if (window.Chart && canvas.getContext) {
      const ctx = canvas.getContext("2d");
      if (state.chart) state.chart.destroy();
      state.chart = new Chart(ctx, {
        type: "line",
        data: { labels, datasets: [{ label: "Signed", data: values }] },
        options: { responsive: true, tension: 0.3 },
      });
    } else if (window.frappe && frappe.Chart) {
      // eslint-disable-next-line no-new
      new frappe.Chart(canvas, { type: "line", data: { labels, datasets: [{ name: "Signed", values }] }, height: 220 });
    } else {
      canvas.outerHTML = `<div class="wd-muted">Chart library not loaded — cards & KPIs are shown.</div>`;
    }
  }

  async function refreshAll() {
    await renderCards();
    await renderTrend();
  }

  function resetFilters() {
    document.getElementById("company").value = "";
    document.getElementById("executive_name").value = "";
    setDefaultDates();
    refreshAll();
  }

  // -------- WIRE UP --------
  setDefaultDates();
  page.body.on("click", "#apply", refreshAll);
  page.body.on("click", "#reset", resetFilters);
  refreshAll();
};
