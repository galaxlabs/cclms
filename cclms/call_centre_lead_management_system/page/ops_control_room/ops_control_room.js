frappe.pages['ops-control-room'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __('OPS Control Room'),
    single_column: true
  });

  frappe.require(['/assets/cclms/js/echarts.min.js'], () => {
    new cclms.OpsControlRoom(page);
  });
};

frappe.provide('cclms');

cclms.OpsControlRoom = class {
  constructor(page) {
    this.page = page;
    this.make_filters();
    this.make_layout();
    this.refresh();
  }

  make_filters() {
    const today = frappe.datetime.get_today(); // YYYY-MM-DD
    const ym = today.slice(0, 7);

    this.month = this.page.add_field({
      label: __('Month'),
      fieldtype: 'Data',
      fieldname: 'month',
      default: ym,
      reqd: 1
    });

    this.operator = this.page.add_field({
      label: __('Operator'),
      fieldtype: 'Link',
      fieldname: 'operator',
      options: 'Operator'
    });

    this.agent = this.page.add_field({
      label: __('Agent'),
      fieldtype: 'Link',
      fieldname: 'agent',
      options: 'User'
    });

    this.metric = this.page.add_field({
      label: __('Trend Metric'),
      fieldtype: 'Select',
      fieldname: 'metric',
      options: ['signed', 'approved', 'installed', 'rejected', 'cancelled', 'agreement_sent', 'converted'].join('\n'),
      default: 'signed'
    });

    this.page.set_primary_action(__('Refresh'), () => this.refresh());
  }

  make_layout() {
    this.page.main.html(`
      <div class="ops-cr">
        <div class="ops-cards" style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;"></div>

        <div style="margin-top:16px; display:grid; grid-template-columns: 2fr 1fr; gap:12px;">
          <div class="ops-chart" style="height:320px;border:1px solid var(--border-color);border-radius:8px;"></div>
          <div class="ops-signed" style="border:1px solid var(--border-color);border-radius:8px;padding:8px;"></div>
        </div>

        <div style="margin-top:12px;">
          <div class="ops-agents" style="border:1px solid var(--border-color);border-radius:8px;padding:8px;"></div>
        </div>
      </div>
    `);

    this.$cards = this.page.main.find('.ops-cards');
    this.$chart = this.page.main.find('.ops-chart')[0];
    this.$signed = this.page.main.find('.ops-signed');
    this.$agents = this.page.main.find('.ops-agents');

    this.chart = echarts.init(this.$chart);
  }

  async refresh() {
    const args = {
      month: this.month.get_value(),
      operator: this.operator.get_value() || null,
      agent: this.agent.get_value() || null
    };

    const kpis = await frappe.call({
      method: 'cclms.api.operator_deal_kpis.monthly_kpis',
      args
    }).then(r => r.message);

    this.render_cards(kpis);

    const metric = this.metric.get_value() || 'signed';
    const trend = await frappe.call({
      method: 'cclms.api.operator_deal_kpis.trend',
      args: { kpi: metric, months_back: 12, operator: args.operator, agent: args.agent }
    }).then(r => (r.message || []).reverse());

    this.render_chart(metric, trend);

    const agents = await frappe.call({
      method: 'cclms.api.operator_deal_kpis.agent_kpis',
      args: { month: args.month, operator: args.operator }
    }).then(r => r.message || []);

    this.render_agent_table(agents);

    // signed drilldown preview (latest 10)
    const signed = await frappe.call({
      method: 'cclms.api.operator_deal_kpis.signed_list',
      args: { month: args.month, operator: args.operator, agent: args.agent, limit: 10 }
    }).then(r => r.message || []);

    this.render_signed_preview(signed);
  }

  render_cards(k) {
    const items = [
      ['Approved', k.approved], ['Rejected', k.rejected],
      ['Agreement Sent', k.agreement_sent], ['Signed', k.signed],
      ['Converted', k.converted], ['Installed', k.installed],
      ['Cancelled', k.cancelled], ['Net Signed', k.net_signed],
    ];

    this.$cards.empty();
    items.forEach(([label, val]) => {
      const clickable = (label === 'Signed');
      this.$cards.append(`
        <div class="ops-card" data-label="${label}" style="cursor:${clickable?'pointer':'default'};border:1px solid var(--border-color);border-radius:8px;padding:12px;">
          <div style="color:var(--text-muted);font-size:12px;">${frappe.utils.escape_html(label)}</div>
          <div style="font-size:24px;font-weight:700;">${val || 0}</div>
        </div>
      `);
    });

    // click "Signed" card => open full list
    this.$cards.find('.ops-card').on('click', (e) => {
      const label = $(e.currentTarget).data('label');
      if (label === 'Signed') this.open_signed_dialog();
    });
  }

  render_chart(metric, rows) {
    const x = rows.map(r => r.ym);
    const y = rows.map(r => r.value);

    this.chart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: x },
      yAxis: { type: 'value' },
      series: [{ type: 'line', data: y, smooth: true }],
      title: { text: `Trend: ${metric}` }
    }, true);
  }

  render_agent_table(rows) {
    const cols = ['agent','posted','approved','agreement_sent','signed','converted','installed','rejected','cancelled','net_signed'];
    let html = `<h5 style="margin:6px 8px;">${__('Agent KPIs')}</h5>`;
    html += `<div style="overflow:auto;"><table class="table table-bordered" style="margin:0;">`;
    html += `<thead><tr>${cols.map(c => `<th>${frappe.utils.escape_html(c)}</th>`).join('')}</tr></thead>`;
    html += `<tbody>`;
    rows.forEach(r => {
      html += `<tr>${cols.map(c => `<td>${frappe.utils.escape_html(String(r[c] ?? ''))}</td>`).join('')}</tr>`;
    });
    html += `</tbody></table></div>`;
    this.$agents.html(html);
  }

  render_signed_preview(rows) {
    let html = `<h5 style="margin:6px 8px;">${__('Latest Signed (this month)')}</h5>`;
    html += `<div style="overflow:auto;"><table class="table table-bordered" style="margin:0;">`;
    html += `<thead><tr><th>Deal</th><th>Operator</th><th>Agent</th><th>Business</th><th>Signed</th></tr></thead>`;
    html += `<tbody>`;
    rows.forEach(r => {
      html += `<tr>
        <td><a href="/app/operator-deal/${encodeURIComponent(r.name)}">${frappe.utils.escape_html(r.name)}</a></td>
        <td>${frappe.utils.escape_html(r.operator_company || '')}</td>
        <td>${frappe.utils.escape_html(r.assigned_agent || '')}</td>
        <td>${frappe.utils.escape_html(r.business_type || '')}</td>
        <td>${frappe.utils.escape_html(String(r.signed_date || ''))}</td>
      </tr>`;
    });
    html += `</tbody></table></div>`;
    this.$signed.html(html);
  }

  async open_signed_dialog() {
    const month = this.month.get_value();
    const operator = this.operator.get_value() || null;
    const agent = this.agent.get_value() || null;

    const d = new frappe.ui.Dialog({
      title: __('Signed List'),
      size: 'large',
      fields: [{ fieldtype: 'HTML', fieldname: 'html' }]
    });

    d.show();
    d.set_message(__('Loading...'));

    const rows = await frappe.call({
      method: 'cclms.api.operator_deal_kpis.signed_list',
      args: { month, operator, agent, limit: 200 }
    }).then(r => r.message || []);

    let html = `<div style="overflow:auto;max-height:60vh"><table class="table table-bordered">`;
    html += `<thead><tr><th>Deal</th><th>Operator</th><th>Agent</th><th>Location</th><th>Business</th><th>Tier</th><th>Signed</th></tr></thead><tbody>`;
    rows.forEach(r => {
      html += `<tr>
        <td><a href="/app/operator-deal/${encodeURIComponent(r.name)}">${frappe.utils.escape_html(r.name)}</a></td>
        <td>${frappe.utils.escape_html(r.operator_company || '')}</td>
        <td>${frappe.utils.escape_html(r.assigned_agent || '')}</td>
        <td>${frappe.utils.escape_html(r.location || '')}</td>
        <td>${frappe.utils.escape_html(r.business_type || '')}</td>
        <td>${frappe.utils.escape_html(r.tier || '')}</td>
        <td>${frappe.utils.escape_html(String(r.signed_date || ''))}</td>
      </tr>`;
    });
    html += `</tbody></table></div>`;
    d.fields_dict.html.$wrapper.html(html);
  }
};
