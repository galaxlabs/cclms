// Workflow Dashboard (single-file version)
// Path: cclms/call_centre_lead_management_system/page/workflow_dashboard/workflow_dashboard.js
// If your Page name is 'workflow-dashboard' (hyphen), change the key below accordingly.

frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
  // Build page shell
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Workflow Analytics",
    single_column: true,
  });

  // Minimal Tailwind-like classes will still render fine in Frappe; it's okay if not present.
  page.body.html(`
    <div id="wd-root" class="p-4">
      <div class="flex items-end gap-3 my-4" id="wd-filters">
        <div>
          <label class="text-xs text-muted">Start</label><br/>
          <input type="date" id="start_date" class="input" />
        </div>
        <div>
          <label class="text-xs text-muted">End</label><br/>
          <input type="date" id="end_date" class="input" />
        </div>
        <div>
          <label class="text-xs text-muted">Branch</label><br/>
          <input type="text" id="branch" class="input" placeholder="Lahore/Karachi" />
        </div>
        <div>
          <label class="text-xs text-muted">Company</label><br/>
          <input type="text" id="company" class="input" placeholder="Bitcoin Depot" />
        </div>
        <div>
          <label class="text-xs text-muted">Executive</label><br/>
          <input type="text" id="executive_name" class="input" placeholder="Agent pseudo name" />
        </div>
        <button id="apply" class="btn btn-primary">Apply</button>
      </div>

      <div id="cards" class="grid grid-cols-2 md:grid-cols-4 gap-3"></div>

      <h3 class="mt-6">Leaderboard (Signed)</h3>
      <div id="leaderboard" class="mt-2"></div>

      <h3 class="mt-6">Monthly Trend (Signed)</h3>
      <div class="mt-2">
        <canvas id="trend_chart" height="120"></canvas>
      </div>
    </div>
  `);

  // --- State ---
  const state = { trendChart: null };

  // --- Helpers ---
  function getFilters() {
    const val = (id) => (document.getElementById(id)?.value || "").trim() || null;
    return {
      start_date: val("start_date"),
      end_date: val("end_date"),
      branch: val("branch"),
      company: val("company"),
      executive_name: val("executive_name"),
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
        message: `Failed calling <b>${frappe.utils.escape_html(method)}</b>. Open console for details.`,
        indicator: "red",
      });
      return null;
    }
  }

  function showSkeleton() {
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
    if (lb) {
      lb.innerHTML = `<div class="text-sm text-muted">Loading…</div>`;
    }
  }

  // --- Renderers ---
  async function renderCards() {
    const args = getFilters();
    const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", args);
    if (!data) return;

    const order = ["Draft", "Submitted", "Approved", "Rejected", "Agreement Sent", "Signed", "Installed"];
    const el = document.getElementById("cards");
    if (!el) return;

    el.innerHTML = "";
    order.forEach((k) => {
      const val = (data.summary && data.summary[k]) || 0;
      el.innerHTML += `
        <div class="rounded-xl shadow p-4">
          <div class="text-sm text-gray-500">${frappe.utils.escape_html(k)}</div>
          <div class="text-2xl font-semibold">${val}</div>
        </div>`;
    });

    // Add a TOTAL card at the end
    el.innerHTML += `
      <div class="rounded-xl shadow p-4">
        <div class="text-sm text-gray-500">Total</div>
        <div class="text-2xl font-semibold">${data.total || 0}</div>
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
      el.innerHTML = `<div class="text-sm text-muted">No data found for current filters.</div>`;
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

    const points = (data && data.points) || [];
    const labels = points.map((p) => p.bucket);
    const values = points.map((p) => p.total);

    // Prefer Chart.js if available; fallback to frappe-charts; otherwise, show note.
    if (window.Chart && canvas.getContext) {
      const ctx = canvas.getContext("2d");
      if (state.trendChart) state.trendChart.destroy();
      state.trendChart = new Chart(ctx, {
        type: "line",
        data: {
          labels,
          datasets: [{ label: "Signed", data: values }],
        },
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
      canvas.outerHTML =
        `<div class="text-sm text-muted">Chart library not loaded — cards & table are shown. (Optional: include Chart.js or use frappe-charts)</div>`;
    }
  }

  async function refreshAll() {
    showSkeleton();
    await renderCards();
    await renderLeaderboard();
    await renderTrend();
  }

  // --- Events ---
  page.body.on("click", "#apply", refreshAll);

  // First load
  refreshAll();
};

// Optional: refresh whenever the page becomes visible again.
frappe.pages["workflow_dashboard"].on_page_show = function () {
  // no-op; add refreshAll() here if you want to re-run on each show
};
// Workflow Dashboard (single-file version)
// Path: cclms/call_centre_lead_management_system/page/workflow_dashboard/workflow_dashboard.js
// If your Page name is 'workflow-dashboard' (hyphen), change the key below accordingly.

frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
  // Build page shell
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Workflow Analytics",
    single_column: true,
  });

  // Minimal Tailwind-like classes will still render fine in Frappe; it's okay if not present.
  page.body.html(`
    <div id="wd-root" class="p-4">
      <div class="flex items-end gap-3 my-4" id="wd-filters">
        <div>
          <label class="text-xs text-muted">Start</label><br/>
          <input type="date" id="start_date" class="input" />
        </div>
        <div>
          <label class="text-xs text-muted">End</label><br/>
          <input type="date" id="end_date" class="input" />
        </div>
        <div>
          <label class="text-xs text-muted">Branch</label><br/>
          <input type="text" id="branch" class="input" placeholder="Lahore/Karachi" />
        </div>
        <div>
          <label class="text-xs text-muted">Company</label><br/>
          <input type="text" id="company" class="input" placeholder="Bitcoin Depot" />
        </div>
        <div>
          <label class="text-xs text-muted">Executive</label><br/>
          <input type="text" id="executive_name" class="input" placeholder="Agent pseudo name" />
        </div>
        <button id="apply" class="btn btn-primary">Apply</button>
      </div>

      <div id="cards" class="grid grid-cols-2 md:grid-cols-4 gap-3"></div>

      <h3 class="mt-6">Leaderboard (Signed)</h3>
      <div id="leaderboard" class="mt-2"></div>

      <h3 class="mt-6">Monthly Trend (Signed)</h3>
      <div class="mt-2">
        <canvas id="trend_chart" height="120"></canvas>
      </div>
    </div>
  `);

  // --- State ---
  const state = { trendChart: null };

  // --- Helpers ---
  function getFilters() {
    const val = (id) => (document.getElementById(id)?.value || "").trim() || null;
    return {
      start_date: val("start_date"),
      end_date: val("end_date"),
      branch: val("branch"),
      company: val("company"),
      executive_name: val("executive_name"),
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
        message: `Failed calling <b>${frappe.utils.escape_html(method)}</b>. Open console for details.`,
        indicator: "red",
      });
      return null;
    }
  }

  function showSkeleton() {
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
    if (lb) {
      lb.innerHTML = `<div class="text-sm text-muted">Loading…</div>`;
    }
  }

  // --- Renderers ---
  async function renderCards() {
    const args = getFilters();
    const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", args);
    if (!data) return;

    const order = ["Draft", "Submitted", "Approved", "Rejected", "Agreement Sent", "Signed", "Installed"];
    const el = document.getElementById("cards");
    if (!el) return;

    el.innerHTML = "";
    order.forEach((k) => {
      const val = (data.summary && data.summary[k]) || 0;
      el.innerHTML += `
        <div class="rounded-xl shadow p-4">
          <div class="text-sm text-gray-500">${frappe.utils.escape_html(k)}</div>
          <div class="text-2xl font-semibold">${val}</div>
        </div>`;
    });

    // Add a TOTAL card at the end
    el.innerHTML += `
      <div class="rounded-xl shadow p-4">
        <div class="text-sm text-gray-500">Total</div>
        <div class="text-2xl font-semibold">${data.total || 0}</div>
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
      el.innerHTML = `<div class="text-sm text-muted">No data found for current filters.</div>`;
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

    const points = (data && data.points) || [];
    const labels = points.map((p) => p.bucket);
    const values = points.map((p) => p.total);

    // Prefer Chart.js if available; fallback to frappe-charts; otherwise, show note.
    if (window.Chart && canvas.getContext) {
      const ctx = canvas.getContext("2d");
      if (state.trendChart) state.trendChart.destroy();
      state.trendChart = new Chart(ctx, {
        type: "line",
        data: {
          labels,
          datasets: [{ label: "Signed", data: values }],
        },
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
      canvas.outerHTML =
        `<div class="text-sm text-muted">Chart library not loaded — cards & table are shown. (Optional: include Chart.js or use frappe-charts)</div>`;
    }
  }

  async function refreshAll() {
    showSkeleton();
    await renderCards();
    await renderLeaderboard();
    await renderTrend();
  }

  // --- Events ---
  page.body.on("click", "#apply", refreshAll);

  // First load
  refreshAll();
};

// Optional: refresh whenever the page becomes visible again.
frappe.pages["workflow_dashboard"].on_page_show = function () {
  // no-op; add refreshAll() here if you want to re-run on each show
};
// Workflow Dashboard (single-file version)
// Path: cclms/call_centre_lead_management_system/page/workflow_dashboard/workflow_dashboard.js
// If your Page name is 'workflow-dashboard' (hyphen), change the key below accordingly.

frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
  // Build page shell
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Workflow Analytics",
    single_column: true,
  });

  // Minimal Tailwind-like classes will still render fine in Frappe; it's okay if not present.
  page.body.html(`
    <div id="wd-root" class="p-4">
      <div class="flex items-end gap-3 my-4" id="wd-filters">
        <div>
          <label class="text-xs text-muted">Start</label><br/>
          <input type="date" id="start_date" class="input" />
        </div>
        <div>
          <label class="text-xs text-muted">End</label><br/>
          <input type="date" id="end_date" class="input" />
        </div>
        <div>
          <label class="text-xs text-muted">Branch</label><br/>
          <input type="text" id="branch" class="input" placeholder="Lahore/Karachi" />
        </div>
        <div>
          <label class="text-xs text-muted">Company</label><br/>
          <input type="text" id="company" class="input" placeholder="Bitcoin Depot" />
        </div>
        <div>
          <label class="text-xs text-muted">Executive</label><br/>
          <input type="text" id="executive_name" class="input" placeholder="Agent pseudo name" />
        </div>
        <button id="apply" class="btn btn-primary">Apply</button>
      </div>

      <div id="cards" class="grid grid-cols-2 md:grid-cols-4 gap-3"></div>

      <h3 class="mt-6">Leaderboard (Signed)</h3>
      <div id="leaderboard" class="mt-2"></div>

      <h3 class="mt-6">Monthly Trend (Signed)</h3>
      <div class="mt-2">
        <canvas id="trend_chart" height="120"></canvas>
      </div>
    </div>
  `);

  // --- State ---
  const state = { trendChart: null };

  // --- Helpers ---
  function getFilters() {
    const val = (id) => (document.getElementById(id)?.value || "").trim() || null;
    return {
      start_date: val("start_date"),
      end_date: val("end_date"),
      branch: val("branch"),
      company: val("company"),
      executive_name: val("executive_name"),
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
        message: `Failed calling <b>${frappe.utils.escape_html(method)}</b>. Open console for details.`,
        indicator: "red",
      });
      return null;
    }
  }

  function showSkeleton() {
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
    if (lb) {
      lb.innerHTML = `<div class="text-sm text-muted">Loading…</div>`;
    }
  }

  // --- Renderers ---
  async function renderCards() {
    const args = getFilters();
    const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", args);
    if (!data) return;

    const order = ["Draft", "Submitted", "Approved", "Rejected", "Agreement Sent", "Signed", "Installed"];
    const el = document.getElementById("cards");
    if (!el) return;

    el.innerHTML = "";
    order.forEach((k) => {
      const val = (data.summary && data.summary[k]) || 0;
      el.innerHTML += `
        <div class="rounded-xl shadow p-4">
          <div class="text-sm text-gray-500">${frappe.utils.escape_html(k)}</div>
          <div class="text-2xl font-semibold">${val}</div>
        </div>`;
    });

    // Add a TOTAL card at the end
    el.innerHTML += `
      <div class="rounded-xl shadow p-4">
        <div class="text-sm text-gray-500">Total</div>
        <div class="text-2xl font-semibold">${data.total || 0}</div>
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
      el.innerHTML = `<div class="text-sm text-muted">No data found for current filters.</div>`;
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

    const points = (data && data.points) || [];
    const labels = points.map((p) => p.bucket);
    const values = points.map((p) => p.total);

    // Prefer Chart.js if available; fallback to frappe-charts; otherwise, show note.
    if (window.Chart && canvas.getContext) {
      const ctx = canvas.getContext("2d");
      if (state.trendChart) state.trendChart.destroy();
      state.trendChart = new Chart(ctx, {
        type: "line",
        data: {
          labels,
          datasets: [{ label: "Signed", data: values }],
        },
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
      canvas.outerHTML =
        `<div class="text-sm text-muted">Chart library not loaded — cards & table are shown. (Optional: include Chart.js or use frappe-charts)</div>`;
    }
  }

  async function refreshAll() {
    showSkeleton();
    await renderCards();
    await renderLeaderboard();
    await renderTrend();
  }

  // --- Events ---
  page.body.on("click", "#apply", refreshAll);

  // First load
  refreshAll();
};

// Optional: refresh whenever the page becomes visible again.
frappe.pages["workflow_dashboard"].on_page_show = function () {
  // no-op; add refreshAll() here if you want to re-run on each show
};
