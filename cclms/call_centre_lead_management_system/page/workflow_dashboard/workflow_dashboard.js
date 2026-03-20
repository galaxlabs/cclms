frappe.pages["workflow_dashboard"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Workflow Dashboard"),
    single_column: true,
  });

  frappe.require(["/assets/cclms/js/echarts.min.js"], () => {
    new cclms.WorkflowDashboardV2(page);
  });
};

frappe.provide("cclms");

cclms.WorkflowDashboardV2 = class {
  constructor(page) {
    this.page = page;
    this.make_filters();
    this.make_layout();
    this.refresh();
  }

  make_filters() {
    const today = frappe.datetime.get_today();
    this.month = this.page.add_field({
      label: __("Month"),
      fieldtype: "Data",
      fieldname: "month",
      default: today.slice(0, 7),
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
      <div class="workflow-v2">
        <div class="wf-cards" style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;"></div>
        <div style="margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:12px;">
          <div class="wf-status" style="border:1px solid var(--border-color);border-radius:10px;padding:10px;"></div>
          <div class="wf-chart" style="height:340px;border:1px solid var(--border-color);border-radius:10px;"></div>
        </div>
        <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:12px;">
          <div class="wf-operators" style="border:1px solid var(--border-color);border-radius:10px;padding:10px;"></div>
          <div class="wf-agents" style="border:1px solid var(--border-color);border-radius:10px;padding:10px;"></div>
        </div>
      </div>
    `);

    this.$cards = this.page.main.find(".wf-cards");
    this.$status = this.page.main.find(".wf-status");
    this.$operators = this.page.main.find(".wf-operators");
    this.$agents = this.page.main.find(".wf-agents");
    this.$chart = this.page.main.find(".wf-chart")[0];
    this.chart = echarts.init(this.$chart);
  }

  get_args() {
    return {
      month: this.month.get_value(),
      operator: this.operator.get_value() || null,
      agent: this.agent.get_value() || null,
    };
  }

  async refresh() {
    const args = this.get_args();

    const [overview, operators, agents, trend] = await Promise.all([
      frappe.call({ method: "cclms.api.page_reporting.overview", args }).then((r) => r.message || {}),
      frappe.call({ method: "cclms.api.page_reporting.company_breakdown", args: { month: args.month, operator: args.operator, agent: args.agent } }).then((r) => r.message || []),
      frappe.call({ method: "cclms.api.page_reporting.agent_breakdown", args: { month: args.month, operator: args.operator } }).then((r) => r.message || []),
      frappe.call({ method: "cclms.api.page_reporting.multi_trend", args: { operator: args.operator, agent: args.agent, months_back: 12 } }).then((r) => r.message || {}),
    ]);

    this.render_cards(overview.counts || {});
    this.render_status(overview.status_snapshot || []);
    this.render_chart(trend);
    this.$operators.html(this.render_table(__("Operator Workflow Summary"), operators, ["operator_company", "submitted", "approved", "agreement_sent", "signed", "converted", "installed", "rejected", "cancelled", "net_signed"]));
    this.$agents.html(this.render_table(__("Agent Workflow Summary"), agents, ["agent", "submitted", "approved", "agreement_sent", "signed", "converted", "installed", "rejected", "cancelled", "net_signed"]));
  }

  render_cards(counts) {
    const items = [
      ["Submitted", counts.submitted || 0],
      ["Approved", counts.approved || 0],
      ["Agreement Sent", counts.agreement_sent || 0],
      ["Signed", counts.signed || 0],
      ["Converted", counts.converted || 0],
      ["Installed", counts.installed || 0],
      ["Rejected", counts.rejected || 0],
      ["Cancelled", counts.cancelled || 0],
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
    let html = `<h5 style="margin:4px 4px 10px 4px;">${__("Current Deal Statuses")}</h5>`;
    html += `<table class="table table-bordered" style="margin:0;"><thead><tr><th>Status</th><th>Count</th></tr></thead><tbody>`;
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

  render_chart(data) {
    this.chart.setOption({
      title: { text: __("Milestone Trend") },
      tooltip: { trigger: "axis" },
      legend: { top: 24 },
      grid: { left: 40, right: 20, top: 60, bottom: 30 },
      xAxis: { type: "category", data: data.categories || [] },
      yAxis: { type: "value" },
      series: (data.series || []).map((item) => ({
        name: item.name,
        type: "bar",
        stack: "total",
        emphasis: { focus: "series" },
        data: item.data || [],
      })),
    }, true);
  }

  render_table(title, rows, cols) {
    let html = `<h5 style="margin:4px 4px 10px 4px;">${frappe.utils.escape_html(title)}</h5>`;
    html += `<div style="overflow:auto;"><table class="table table-bordered" style="margin:0;"><thead><tr>`;
    html += cols.map((col) => `<th>${frappe.utils.escape_html(col.replace(/_/g, " "))}</th>`).join("");
    html += `</tr></thead><tbody>`;

    if (!rows.length) {
      html += `<tr><td colspan="${cols.length}" class="text-muted">${__("No rows found")}</td></tr>`;
    } else {
      rows.forEach((row) => {
        html += `<tr>${cols.map((col) => `<td>${frappe.utils.escape_html(String(row[col] ?? ""))}</td>`).join("")}</tr>`;
      });
    }

    html += `</tbody></table></div>`;
    return html;
  }
};
