frappe.provide("cclms.ui");

cclms.ui.getFilters = () => ({
  start_date: document.getElementById("start_date").value || null,
  end_date: document.getElementById("end_date").value || null,
  branch: document.getElementById("branch").value || null,
  company: document.getElementById("company").value || null,
  executive_name: document.getElementById("executive_name").value || null,
});

async function call(method, args = {}) {
  const res = await frappe.call({ method, args });
  return res.message;
}

async function renderCards() {
  const args = cclms.ui.getFilters();
  const data = await call("cclms.api.reports.workflow_summary.get_workflow_summary", args);

  const order = ["Draft","Submitted","Approved","Rejected","Agreement Sent","Signed","Installed"];
  const el = document.getElementById("cards");
  el.innerHTML = "";

  order.forEach(k => {
    const val = data.summary[k] || 0;
    el.innerHTML += `
      <div class="rounded-xl shadow p-4">
        <div class="text-sm text-gray-500">${k}</div>
        <div class="text-2xl font-semibold">${val}</div>
      </div>`;
  });
}

async function renderLeaderboard() {
  const args = cclms.ui.getFilters();
  const data = await call("cclms.api.reports.agent_performance.get_agent_performance", {
    ...args, state: "Signed"
  });

  const el = document.getElementById("leaderboard");
  el.innerHTML = `
    <table class="w-full table-auto border">
      <thead>
        <tr><th class="p-2 text-left">Executive</th><th class="p-2 text-right">Signed</th></tr>
      </thead>
      <tbody>
        ${data.rows.map(r => `
          <tr>
            <td class="p-2">${r.executive_name || "-"}</td>
            <td class="p-2 text-right">${r.total}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

let trendChart = null;
async function renderTrend() {
  const args = cclms.ui.getFilters();
  const data = await call("cclms.api.reports.timeline_trends.get_timeline_trends", {
    ...args, state: "Signed", months: 6
  });

  const labels = data.points.map(p => p.bucket);
  const values = data.points.map(p => p.total);

  // use plain Chart.js or frappe-charts if available; here assume Chart.js is loaded
  const ctx = document.getElementById("trend_chart").getContext("2d");
  if (trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets: [{ label: "Signed", data: values }] },
    options: { responsive: true, tension: 0.3 }
  });
}

async function refreshAll() {
  await renderCards();
  await renderLeaderboard();
  await renderTrend();
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("apply");
  btn.addEventListener("click", refreshAll);
  refreshAll();
});
