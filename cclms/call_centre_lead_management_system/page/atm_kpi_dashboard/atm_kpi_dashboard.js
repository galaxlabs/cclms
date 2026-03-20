frappe.pages["atm-kpi-dashboard"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("ATM KPI Dashboard"),
    single_column: true,
  });

  frappe.require(["/assets/cclms/js/echarts.min.js"], () => {
    new cclms.ATMKPIDashboard(page);
  });
};

frappe.provide("cclms");

cclms.ATMKPIDashboard = class {
  constructor(page) {
    this.page = page;
    this.make_filters();
    this.make_layout();
    this.apply_route_options();
    this.refresh();
  }

  make_filters() {
    const today = frappe.datetime.get_today();
    const monthStart = `${today.slice(0, 8)}01`;

    this.fromDate = this.page.add_field({
      label: __("From Date"),
      fieldtype: "Date",
      fieldname: "from_date",
      default: monthStart,
      reqd: 1,
    });

    this.toDate = this.page.add_field({
      label: __("To Date"),
      fieldtype: "Date",
      fieldname: "to_date",
      default: today,
      reqd: 1,
    });

    this.operator = this.page.add_field({
      label: __("Operator"),
      fieldtype: "Link",
      fieldname: "operator",
      options: "Operator",
    });

    this.agent = this.page.add_field({
      label: __("Sales Agent"),
      fieldtype: "Link",
      fieldname: "agent",
      options: "Sales Agent",
    });

    this.page.set_primary_action(__("Refresh"), () => this.refresh());
  }

  make_layout() {
    this.page.main.html(`
      <div class="atm-kpi-v2">
        <div class="kpi-cards" style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;"></div>

        <div style="margin-top:16px;display:grid;grid-template-columns:2fr 1fr;gap:12px;">
          <div class="kpi-trend" style="height:340px;border:1px solid var(--border-color);border-radius:10px;"></div>
          <div class="kpi-status" style="border:1px solid var(--border-color);border-radius:10px;padding:10px;"></div>
        </div>

        <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:12px;">
          <div class="kpi-operators" style="border:1px solid var(--border-color);border-radius:10px;padding:10px;"></div>
          <div class="kpi-agents" style="border:1px solid var(--border-color);border-radius:10px;padding:10px;"></div>
        </div>

        <div style="margin-top:12px;">
          <div class="kpi-signed" style="border:1px solid var(--border-color);border-radius:10px;padding:10px;"></div>
        </div>
      </div>
    `);

    this.$cards = this.page.main.find(".kpi-cards");
    this.$trend = this.page.main.find(".kpi-trend")[0];
    this.$status = this.page.main.find(".kpi-status");
    this.$operators = this.page.main.find(".kpi-operators");
    this.$agents = this.page.main.find(".kpi-agents");
    this.$signed = this.page.main.find(".kpi-signed");
    this.chart = echarts.init(this.$trend);
  }

  apply_route_options() {
    const routeOptions = frappe.route_options || {};
    if (routeOptions.from_date) this.fromDate.set_value(routeOptions.from_date);
    if (routeOptions.to_date) this.toDate.set_value(routeOptions.to_date);
    if (routeOptions.operator) this.operator.set_value(routeOptions.operator);
    if (routeOptions.agent) this.agent.set_value(routeOptions.agent);
  }

  get_args() {
    return {
      start_date: this.fromDate.get_value(),
      end_date: this.toDate.get_value(),
      operator: this.operator.get_value() || null,
      agent: this.agent.get_value() || null,
    };
  }

  async refresh() {
    const args = this.get_args();

    const [overview, trend, operators, agents, signed] = await Promise.all([
      frappe.call({ method: "cclms.api.page_reporting.overview", args }).then((r) => r.message || {}),
      frappe.call({ method: "cclms.api.page_reporting.multi_trend", args: { operator: args.operator, agent: args.agent, months_back: 12 } }).then((r) => r.message || {}),
      frappe.call({ method: "cclms.api.page_reporting.company_breakdown", args: { start_date: args.start_date, end_date: args.end_date, operator: args.operator, agent: args.agent } }).then((r) => r.message || []),
      frappe.call({ method: "cclms.api.page_reporting.agent_breakdown", args: { start_date: args.start_date, end_date: args.end_date, operator: args.operator } }).then((r) => r.message || []),
      frappe.call({ method: "cclms.api.page_reporting.recent_signed", args: { ...args, limit: 20 } }).then((r) => r.message || []),
    ]);

    this.render_cards(overview.counts || {});
    this.render_status(overview.status_snapshot || []);
    this.render_trend(trend);
    this.render_operator_table(operators);
    this.render_agent_table(agents);
    this.render_signed_table(signed);
  }

  render_cards(counts) {
    const items = [
      ["Submitted", counts.submitted || 0],
      ["Approved", counts.approved || 0],
      ["Agreement Sent", counts.agreement_sent || 0],
      ["Signed", counts.signed || 0],
      ["Installed", counts.installed || 0],
      ["Rejected", counts.rejected || 0],
      ["Cancelled", counts.cancelled || 0],
      ["Converted", counts.converted || 0],
      ["Disputed", counts.disputed || 0],
      ["Net Signed", counts.net_signed || 0],
    ];

    this.$cards.empty();
    items.forEach(([label, value]) => {
      this.$cards.append(`
        <div style="border:1px solid var(--border-color);border-radius:10px;padding:12px;background:#fff;">
          <div style="font-size:12px;color:var(--text-muted);">${frappe.utils.escape_html(label)}</div>
          <div style="font-size:28px;font-weight:700;">${value}</div>
        </div>
      `);
    });
  }

  render_status(rows) {
    let html = `<h5 style="margin:4px 4px 10px 4px;">${__("Current Status Snapshot")}</h5>`;
    html += `<table class="table table-bordered" style="margin:0;"><thead><tr><th>Status</th><th>Deals</th></tr></thead><tbody>`;
    if (!rows.length) {
      html += `<tr><td colspan="2" class="text-muted">${__("No data")}</td></tr>`;
    } else {
      rows.forEach((row) => {
        html += `<tr><td>${frappe.utils.escape_html(row.label || "")}</td><td>${frappe.utils.escape_html(String(row.value || 0))}</td></tr>`;
      });
    }
    html += `</tbody></table>`;
    this.$status.html(html);
  }

  render_trend(data) {
    const categories = data.categories || [];
    const series = (data.series || []).map((item) => ({
      name: item.name,
      type: "line",
      smooth: true,
      data: item.data || [],
    }));

    this.chart.setOption({
      title: { text: __("Milestone Trend") },
      tooltip: { trigger: "axis" },
      legend: { top: 24 },
      grid: { left: 40, right: 20, top: 60, bottom: 30 },
      xAxis: { type: "category", data: categories },
      yAxis: { type: "value" },
      series,
    }, true);
  }

  render_operator_table(rows) {
    const cols = ["operator_company", "submitted", "approved", "agreement_sent", "signed", "installed", "rejected", "cancelled", "net_signed"];
    this.$operators.html(this.make_table(__("Operator Breakdown"), cols, rows));
  }

  render_agent_table(rows) {
    const cols = ["agent", "submitted", "approved", "agreement_sent", "signed", "installed", "rejected", "cancelled", "net_signed"];
    this.$agents.html(this.make_table(__("Agent Breakdown"), cols, rows));
  }

  render_signed_table(rows) {
    let html = `<h5 style="margin:4px 4px 10px 4px;">${__("Recent Signed Deals")}</h5>`;
    html += `<div style="overflow:auto;"><table class="table table-bordered" style="margin:0;">`;
    html += `<thead><tr><th>Deal</th><th>Operator</th><th>Agent</th><th>Location</th><th>Signed</th><th>Installed</th></tr></thead><tbody>`;
    if (!rows.length) {
      html += `<tr><td colspan="6" class="text-muted">${__("No signed deals in this range")}</td></tr>`;
    } else {
      rows.forEach((row) => {
        html += `<tr>
          <td><a href="/app/operator-deal/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a></td>
          <td>${frappe.utils.escape_html(row.operator_company || "")}</td>
          <td>${frappe.utils.escape_html(row.sales_agent || row.sales_agent_name_text || row.assigned_agent || "")}</td>
          <td>${frappe.utils.escape_html(row.location || "")}</td>
          <td>${frappe.utils.escape_html(String(row.signed_date || ""))}</td>
          <td>${frappe.utils.escape_html(String(row.installed_date || ""))}</td>
        </tr>`;
      });
    }
    html += `</tbody></table></div>`;
    this.$signed.html(html);
  }

  make_table(title, cols, rows) {
    let html = `<h5 style="margin:4px 4px 10px 4px;">${frappe.utils.escape_html(title)}</h5>`;
    html += `<div style="overflow:auto;"><table class="table table-bordered" style="margin:0;"><thead><tr>`;
    html += cols.map((col) => `<th>${frappe.utils.escape_html(col.replace(/_/g, " "))}</th>`).join("");
    html += `</tr></thead><tbody>`;

    if (!rows.length) {
      html += `<tr><td colspan="${cols.length}" class="text-muted">${__("No data")}</td></tr>`;
    } else {
      rows.forEach((row) => {
        html += `<tr>${cols.map((col) => `<td>${frappe.utils.escape_html(String(row[col] ?? ""))}</td>`).join("")}</tr>`;
      });
    }

    html += `</tbody></table></div>`;
    return html;
  }
};
