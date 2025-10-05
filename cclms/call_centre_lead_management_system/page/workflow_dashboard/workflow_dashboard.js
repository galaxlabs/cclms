// Workflow Dashboard — single-file page script
// Place at: cclms/call_centre_lead_management_system/page/workflow_dashboard/workflow_dashboard.js
// If your Page name is "workflow-dashboard" (hyphen), use: frappe.pages["workflow-dashboard"] instead.
frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
  // -------- CONFIG --------
  const DATE_FIELD = "sign_date"; // <-- analysis date field
  const SHOW_STATES_IN_ORDER = [
    "Submitted",
    "Approved",
    "Rejected",
    "Agreement Sent",
    "Signed",
    "Installed",
  ]; // Draft intentionally excluded

  // -------- PAGE SHELL --------
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Workflow Analytics",
    single_column: true,
  });

  page.body.html(`
    <div id="wd-root" class="p-4">
      <div class="flex items-end gap-3 my-4" id="wd-filters">
        <div>
          <label class="text-xs text-muted">Start</label><br/>
          <input type="date" id="start_date" class="input input-xs" />
        </div>
        <div>
          <label class="text-xs text-muted">End</label><br/>
          <input type="date" id="end_date" class="input input-xs" />
        </div>
        <div>
          <label class="text-xs text-muted">Company</label><br/>
          <input type="text" id="company" class="input input-xs" placeholder="Company" />
        </div>
        <div>
          <label class="text-xs text-muted">Executive</label><br/>
          <input type="text" id="executive_name" class="input input-xs" placeholder="Agent pseudo name" />
        </div>
        <button id="apply" class="btn btn-primary btn-sm">Apply</button>
        <button id="reset" class="btn btn-default btn-sm">Reset</button>
      </div>

      <div id="cards" class="grid grid-cols-2 md:grid-cols-4 gap-3"></div>

      <h3 class="mt-6">Leaderboard (Signed)</h3>
      <div id="leaderboard" class="mt-2"></div>

      <h3 class="mt-6">Monthly Trend (Signed)</h3>
      <div class="mt-2">
        <canvas id="trend_chart" height="140"></canvas>
      </div>
    </div>
  `);

  // -------- STATE --------
  const state = { chart: null };

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
  function val(id) {
    return (document.getElementById(id)?.value || "").trim() || null;
  }
  function getFilters() {
    return {
      start_date: val("start_date"),
      end_date: val("end_date"),
      company: val("company"),
      executive_name: val("executive_name"),
      date_field: DATE_FIELD,
    };
  }
  async function call(method, args = {}) {
    try {
      const res = await frappe.call({ method, args, freeze: false });
      return res?.message;
    } catch (e) {
      console.error("[Workflow Dashboard] API error:", method, e);
      frappe.msgprint({
        title: "API Error",
        message: `Failed calling <b>${frappe.utils.escape_html(method)}</b>. See console for details.`,
        indicator: "red",
      });
      return null;
    }
  }
  function skeleton() {
    const cards = document.getElementById("cards");
    if (cards) {
      cards.innerHTML = Array.from({ length: 6 })
        .map(
          () => `
          <div class="rounded-xl shadow p-4">
            <div class="text-sm text-muted">Loading…</div>
            <div class="text-2xl font-semibold">—</div>
          </div>`
        )
        .join("");
    }
    const lb = document.getElementById("leaderboard");
    if (lb) lb.innerHTML = `<div class="text-sm text-muted">Loading…</div>`;
    const canvas = document.getElementById("trend_chart");
    if (canvas && canvas.getContext) {
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }
  }

  // -------- RENDERERS --------
  async function renderCards() {
    const args = getFilters();
    const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", args);
    const el = document.getElementById("cards");
    if (!el) return;

    if (!data || !data.summary) {
      el.innerHTML = `<div class="text-sm text-muted">No data.</div>`;
      return;
    }

    // Remove Drafts and compute total without Draft
    const summary = { ...data.summary };
    delete summary["Draft"]; // <- hide "Draft" everywhere

    // Create cards in our desired order; include any unexpected states at the end
    const ordered = [];
    SHOW_STATES_IN_ORDER.forEach((s) => {
      if (summary[s] != null) ordered.push({ state: s, total: summary[s] });
    });
    Object.keys(summary).forEach((s) => {
      if (!SHOW_STATES_IN_ORDER.includes(s)) {
        ordered.push({ state: s, total: summary[s] });
      }
    });

    // Compute total without drafts
    const totalNoDraft = ordered.reduce((a, b) => a + (parseInt(b.total, 10) || 0), 0);

    el.innerHTML = "";
    ordered.forEach((row) => {
      const val = parseInt(row.total, 10) || 0;
      el.innerHTML += `
        <div class="rounded-xl shadow p-4">
          <div class="text-sm text-gray-500">${frappe.utils.escape_html(row.state)}</div>
          <div class="text-2xl font-semibold">${val}</div>
        </div>`;
    });
    el.innerHTML += `
      <div class="rounded-xl shadow p-4">
        <div class="text-sm text-gray-500">Total (No Draft)</div>
        <div class="text-2xl font-semibold">${totalNoDraft}</div>
      </div>`;
  }

  async function renderLeaderboard() {
    const args = getFilters();
    const data = await call("cclms.api.reports.agent_performance.get_agent_performance", {
      ...args,
      state: "Signed",
    });
    const el = document.getElementById("leaderboard");
    if (!el) return;

    const rows = (data && data.rows) || [];
    if (!rows.length) {
      el.innerHTML = `<div class="text-sm text-muted">No data for current filters.</div>`;
      return;
    }

    el.innerHTML = `
      <table class="w-full table-bordered">
        <thead>
          <tr>
            <th class="p-2 text-left">Executive</th>
            <th class="p-2 text-right">Signed</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (r) => `
            <tr>
              <td class="p-2">${frappe.utils.escape_html(r.executive_name || "-")}</td>
              <td class="p-2 text-right">${r.total}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
  }

  async function renderTrend() {
    const args = getFilters();
    const data = await call("cclms.api.reports.timeline_trends.get_timeline_trends", {
      ...args,
      state: "Signed",
      months: 6,
    });

    const canvas = document.getElementById("trend_chart");
    if (!canvas) return;

    if (!data || !data.points || !data.points.length) {
      canvas.outerHTML = `<div class="text-sm text-muted">No trend data for current filters.</div>`;
      return;
    }

    const labels = data.points.map((p) => p.bucket);
    const values = data.points.map((p) => p.total);

    // Prefer Chart.js if present; fallback to frappe-charts; else show note
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
      new frappe.Chart(canvas, {
        type: "line",
        data: { labels, datasets: [{ name: "Signed", values }] },
        height: 220,
      });
    } else {
      canvas.outerHTML = `<div class="text-sm text-muted">Chart library not loaded — cards & table are shown.</div>`;
    }
  }

  async function refreshAll() {
    skeleton();
    await renderCards();
    await renderLeaderboard();
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

  // initial run
  refreshAll();
};

// (Optional) refresh every time the page is shown
frappe.pages["workflow_dashboard"].on_page_show = function () {
  // You can call refreshAll() here if you want to auto-refresh on revisit.
};
