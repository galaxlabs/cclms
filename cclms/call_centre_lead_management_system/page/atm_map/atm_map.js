frappe.pages["atm_map"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("ATM Map Ops"),
    single_column: true,
  });

  new cclms.ATMMapOps(page);
};

frappe.provide("cclms");

cclms.ATMMapOps = class {
  constructor(page) {
    this.page = page;
    this.make_actions();
    this.make_layout();
    this.refresh();
  }

  make_actions() {
    this.page.set_primary_action(__("Open Scouting Map"), () => {
      frappe.set_route("atm_scouting");
    });

    this.page.add_action_item(__("Update Competitor Density"), () => {
      frappe.call({
        method: "cclms.api.ops.run_update_competitor_density",
        callback: (r) => frappe.msgprint(__("Done: {0}", [JSON.stringify(r.message || {})])),
      });
    });

    this.page.add_action_item(__("Update Totals"), () => {
      frappe.call({
        method: "cclms.api.ops.run_update_totals",
        callback: (r) => frappe.msgprint(__("Done: {0}", [JSON.stringify(r.message || {})])),
      });
    });

    this.page.add_action_item(__("Apply Rules"), () => {
      frappe.call({
        method: "cclms.api.ops.run_apply_rules",
        callback: (r) => frappe.msgprint(__("Done: {0}", [JSON.stringify(r.message || {})])),
      });
    });
  }

  make_layout() {
    this.page.main.html(`
      <div class="atm-map-ops">
        <div class="map-cards" style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;"></div>
        <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:12px;">
          <div class="map-zones" style="border:1px solid var(--border-color);border-radius:10px;padding:10px;"></div>
          <div class="map-links" style="border:1px solid var(--border-color);border-radius:10px;padding:10px;"></div>
        </div>
      </div>
    `);

    this.$cards = this.page.main.find(".map-cards");
    this.$zones = this.page.main.find(".map-zones");
    this.$links = this.page.main.find(".map-links");
  }

  async refresh() {
    const data = await frappe.call({
      method: "cclms.api.page_reporting.zip_analytics_overview",
    }).then((r) => r.message || {});

    const totals = data.totals || {};
    this.render_cards([
      ["Total ZIPs", totals.total_zips || 0],
      ["Actionable ZIPs", totals.actionable_zips || 0],
      ["With Competitors", totals.zips_with_competitors || 0],
      ["With Our Kiosks", totals.zips_with_our_kiosks || 0],
    ]);
    this.render_zones(data.zones || []);
    this.render_links();
  }

  render_cards(items) {
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

  render_zones(rows) {
    let html = `<h5 style="margin:4px 4px 10px 4px;">${__("Zone Accuracy Summary")}</h5>`;
    html += `<table class="table table-bordered" style="margin:0;"><thead><tr><th>Zone</th><th>Total</th><th>Avg ZIP Score</th><th>Avg Competitor Density</th></tr></thead><tbody>`;
    if (!rows.length) {
      html += `<tr><td colspan="4" class="text-muted">${__("No data")}</td></tr>`;
    } else {
      rows.forEach((row) => {
        html += `<tr>
          <td>${frappe.utils.escape_html(row.zone || "")}</td>
          <td>${frappe.utils.escape_html(String(row.total || 0))}</td>
          <td>${frappe.utils.escape_html(String(row.avg_zip_score || 0))}</td>
          <td>${frappe.utils.escape_html(String(row.avg_competitor_density || 0))}</td>
        </tr>`;
      });
    }
    html += `</tbody></table>`;
    this.$zones.html(html);
  }

  render_links() {
    this.$links.html(`
      <h5 style="margin:4px 4px 10px 4px;">${__("Map Workflow")}</h5>
      <p class="text-muted">${__("Use this page for ZIP health and maintenance, then move into the scouting map for actual location review.")}</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <a class="btn btn-default btn-sm" href="/app/atm_scouting">${__("Open ATM Scouting")}</a>
        <a class="btn btn-default btn-sm" href="/app/agent-command-centre">${__("Open Agent Command Centre")}</a>
        <a class="btn btn-default btn-sm" href="/app/ops-control-room">${__("Open Ops Control Room")}</a>
      </div>
    `);
  }
};
