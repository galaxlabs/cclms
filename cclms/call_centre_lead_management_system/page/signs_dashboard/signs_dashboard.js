frappe.pages["signs-dashboard"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Signs & Attribution Dashboard"),
    single_column: true,
  });
  new SignsDashboard(page);
};

class SignsDashboard {
  constructor(page) {
    this.page = page;
    this._makeFilters();
    this._makeLayout();
    this.refresh();
  }

  // ── Filters ────────────────────────────────────────────────────────────
  _makeFilters() {
    const today = frappe.datetime.get_today();
    const mStart = today.slice(0, 7) + "-01";
    const mEnd   = today;

    this.f_from = this.page.add_field({
      label: __("From Date"), fieldtype: "Date", fieldname: "from_date", default: mStart,
      change: () => this.refresh(),
    });
    this.f_to = this.page.add_field({
      label: __("To Date"), fieldtype: "Date", fieldname: "to_date", default: mEnd,
      change: () => this.refresh(),
    });
    this.f_company = this.page.add_field({
      label: __("Company"), fieldtype: "Link", fieldname: "company",
      options: "Operator Companies", change: () => this.refresh(),
    });
    this.f_branch = this.page.add_field({
      label: __("Branch"), fieldtype: "Link", fieldname: "branch",
      options: "Branch", change: () => this.refresh(),
    });
    this.page.set_primary_action(__("Refresh"), () => this.refresh());
  }

  _args() {
    return {
      from_date: this.f_from.get_value() || null,
      to_date:   this.f_to.get_value()   || null,
      company:   this.f_company.get_value() || null,
      branch:    this.f_branch.get_value()  || null,
    };
  }

  // ── Layout skeleton ────────────────────────────────────────────────────
  _makeLayout() {
    this.page.main.html(`
      <div class="sd-root" style="padding:0 4px;">

        <!-- Summary cards -->
        <div class="sd-cards" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:16px;"></div>

        <!-- Row 2: velocity bar + pipeline snapshot -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
          <div class="sd-panel">
            <div class="sd-panel-title">${__("Avg Days per Stage (from Ledger)")}</div>
            <div class="sd-velocity"></div>
          </div>
          <div class="sd-panel">
            <div class="sd-panel-title">${__("Live Pipeline Snapshot")}</div>
            <div class="sd-pipeline"></div>
          </div>
        </div>

        <!-- Row 3: approval/rejection trend -->
        <div class="sd-panel" style="margin-bottom:16px;">
          <div class="sd-panel-title">${__("Monthly Approval / Rejection / Signed Trend")}</div>
          <div class="sd-trend" style="height:260px;"></div>
        </div>

        <!-- Row 4: attribution table + pending signs -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
          <div class="sd-panel">
            <div class="sd-panel-title">${__("Agent Attribution")}</div>
            <div class="sd-attribution"></div>
          </div>
          <div class="sd-panel">
            <div class="sd-panel-title">${__("Signs Pending Commission Attribution")}
              <span class="sd-pending-badge" style="background:#ef4444;color:#fff;border-radius:999px;padding:1px 8px;font-size:11px;margin-left:6px;">0</span>
            </div>
            <div class="sd-pending"></div>
          </div>
        </div>

      </div>
    `);

    // Style helper
    this.page.main.find(".sd-panel").css({
      border: "1px solid var(--border-color)",
      borderRadius: "10px",
      padding: "12px",
      background: "#fff",
    });
    this.page.main.find(".sd-panel-title").css({
      fontWeight: "600",
      fontSize: "13px",
      marginBottom: "10px",
      color: "var(--text-color)",
    });
  }

  // ── Refresh all sections ───────────────────────────────────────────────
  async refresh() {
    const args = this._args();
    const base = "cclms.call_centre_lead_management_system.page.signs_dashboard.signs_dashboard";

    this._showLoading();

    try {
      const [summary, velocity, pipeline, trend, attribution] = await Promise.all([
        frappe.call({ method: `${base}.get_signs_summary`,            args }).then(r => r.message || {}),
        frappe.call({ method: `${base}.get_stage_velocity`,           args }).then(r => r.message || []),
        frappe.call({ method: `${base}.get_pipeline_snapshot`,        args }).then(r => r.message || {}),
        frappe.call({ method: `${base}.get_approval_rejection_trend`, args: { months_back: 6, company: args.company } }).then(r => r.message || {}),
        frappe.call({ method: `${base}.get_agent_attribution`,        args }).then(r => r.message || []),
      ]);

      this._renderCards(summary, pipeline);
      this._renderVelocity(velocity);
      this._renderPipeline(pipeline);
      this._renderTrend(trend);
      this._renderAttribution(attribution);
      this._renderPending(summary.pending_records || []);
    } catch (e) {
      console.error("Signs dashboard error", e);
      frappe.msgprint(__("Failed to load dashboard data. Check console."), __("Error"));
    }
  }

  _showLoading() {
    this.page.main.find(".sd-cards").html(
      `<div style="grid-column:1/-1;color:var(--text-muted);padding:16px">${frappe.utils.icon("loading", "sm")} ${__("Loading…")}</div>`
    );
  }

  // ── Cards ──────────────────────────────────────────────────────────────
  _renderCards(summary, pipeline) {
    const COLORS = {
      "Signs This Period": "#10b981",
      "Pending Attribution": "#ef4444",
      "Attribution Done": "#22c55e",
      "Sign Rate": "#f59e0b",
      "Rejection Rate": "#ef4444",
      "Total Active Leads": "#3b82f6",
    };
    const items = [
      { label: __("Signs This Period"),   value: summary.total_signs || 0 },
      { label: __("Pending Attribution"), value: summary.pending_attribution || 0, sub: __("no closing agent") },
      { label: __("Attribution Done"),    value: summary.attributed || 0 },
      { label: __("Sign Rate"),           value: (pipeline.sign_rate || 0) + "%" },
      { label: __("Rejection Rate"),      value: (pipeline.rejection_rate || 0) + "%" },
      { label: __("Total Active Leads"),  value: pipeline.total || 0 },
    ];

    const $c = this.page.main.find(".sd-cards").empty();
    items.forEach(({ label, value, sub }) => {
      const color = COLORS[label] || "#334155";
      $c.append(`
        <div style="border:1px solid var(--border-color);border-radius:10px;padding:14px;background:#fff;">
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">${frappe.utils.escape_html(label)}</div>
          <div style="font-size:26px;font-weight:700;color:${color};">${frappe.utils.escape_html(String(value))}</div>
          ${sub ? `<div style="font-size:11px;color:var(--text-muted);">${frappe.utils.escape_html(sub)}</div>` : ""}
        </div>
      `);
    });
  }

  // ── Stage Velocity (horizontal bar) ───────────────────────────────────
  _renderVelocity(rows) {
    const $el = this.page.main.find(".sd-velocity").empty();
    if (!rows.length) {
      $el.html(`<div style="color:var(--text-muted);padding:8px">${__("No ledger data for this period")}</div>`);
      return;
    }

    const MAX_AVG = Math.max(...rows.map(r => r.avg_days)) || 1;
    const TOP_N = rows.slice(0, 12); // max 12 stages

    let html = `<table style="width:100%;font-size:12px;border-collapse:collapse;">`;
    TOP_N.forEach(r => {
      const pct = Math.round((r.avg_days / MAX_AVG) * 100);
      const color = r.avg_days > 14 ? "#ef4444" : r.avg_days > 7 ? "#f59e0b" : "#10b981";
      html += `
        <tr style="border-bottom:1px solid var(--border-color);">
          <td style="width:130px;padding:5px 8px 5px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:130px;"
              title="${frappe.utils.escape_html(r.state)}">${frappe.utils.escape_html(r.state)}</td>
          <td style="padding:5px 4px;">
            <div style="background:var(--bg-color);border-radius:4px;height:14px;width:100%;position:relative;">
              <div style="background:${color};border-radius:4px;height:14px;width:${pct}%;"></div>
            </div>
          </td>
          <td style="width:90px;text-align:right;padding:5px 0 5px 6px;font-weight:600;color:${color};">
            ${r.avg_days}d avg
          </td>
          <td style="width:60px;text-align:right;padding:5px 0 5px 6px;color:var(--text-muted);">
            (${r.transitions})
          </td>
        </tr>`;
    });
    html += `</table>`;
    $el.html(html);
  }

  // ── Pipeline Snapshot (state counts) ──────────────────────────────────
  _renderPipeline(data) {
    const $el = this.page.main.find(".sd-pipeline").empty();
    const rows = data.states || [];
    if (!rows.length) {
      $el.html(`<div style="color:var(--text-muted);padding:8px">${__("No active leads")}</div>`);
      return;
    }

    const STATE_COLORS = {
      "Signed": "#10b981", "Installed": "#22c55e", "Converted": "#0ea5e9",
      "Approved": "#f59e0b", "Rejected": "#ef4444", "Draft": "#6b7280",
      "Pending": "#3b82f6", "Agreement Sent": "#005c08", "Cancelled": "#9ca3af",
    };
    const MAX = Math.max(...rows.map(r => r.count)) || 1;
    const total = data.total || 1;

    let html = `<table style="width:100%;font-size:12px;border-collapse:collapse;">`;
    rows.slice(0, 15).forEach(r => {
      const pct = Math.round((r.count / MAX) * 100);
      const share = Math.round((r.count / total) * 100);
      const color = STATE_COLORS[r.state] || "#6366f1";
      html += `
        <tr style="border-bottom:1px solid var(--border-color);">
          <td style="width:160px;padding:5px 8px 5px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:160px;"
              title="${frappe.utils.escape_html(r.state)}">${frappe.utils.escape_html(r.state)}</td>
          <td style="padding:5px 4px;">
            <div style="background:var(--bg-color);border-radius:4px;height:12px;width:100%;position:relative;">
              <div style="background:${color};border-radius:4px;height:12px;width:${pct}%;"></div>
            </div>
          </td>
          <td style="width:50px;text-align:right;padding:5px 0 5px 6px;font-weight:600;">${r.count}</td>
          <td style="width:40px;text-align:right;padding:5px 0 5px 4px;color:var(--text-muted);">${share}%</td>
        </tr>`;
    });
    html += `</table>`;
    $el.html(html);
  }

  // ── Trend chart (monthly) ──────────────────────────────────────────────
  _renderTrend(data) {
    const $el = this.page.main.find(".sd-trend").empty();
    const cats = data.categories || [];
    const series = data.series || [];

    if (!cats.length) {
      $el.html(`<div style="color:var(--text-muted);padding:8px">${__("No trend data")}</div>`);
      return;
    }

    // Native chart using frappe Charts SVG (no ECharts dependency on this page)
    const canvas = document.createElement("canvas");
    canvas.width = $el.width() || 600;
    canvas.height = 240;
    $el.append(canvas);

    // Build simple HTML table chart as fallback (reliable without extra deps)
    $el.empty();
    const colW = Math.max(60, Math.floor(($el.width() || 600) / cats.length));

    // Find max for scaling
    const allVals = series.flatMap(s => s.data);
    const MAX = Math.max(...allVals, 1);

    let html = `<div style="overflow-x:auto;"><div style="display:flex;align-items:flex-end;gap:2px;height:180px;padding:0 4px;">`;
    cats.forEach((cat, ci) => {
      html += `<div style="display:flex;flex-direction:column;align-items:center;flex:1;min-width:40px;">
        <div style="display:flex;align-items:flex-end;gap:2px;height:160px;">`;
      series.forEach(s => {
        const val = s.data[ci] || 0;
        const h = Math.round((val / MAX) * 140);
        html += `<div title="${frappe.utils.escape_html(s.name)}: ${val}"
                      style="width:10px;height:${h}px;background:${s.color || "#6b7280"};border-radius:2px 2px 0 0;"></div>`;
      });
      html += `</div><div style="font-size:10px;color:var(--text-muted);margin-top:4px;transform:rotate(-45deg);white-space:nowrap;">${frappe.utils.escape_html(cat)}</div></div>`;
    });
    html += `</div>`;

    // Legend
    html += `<div style="display:flex;gap:12px;margin-top:24px;flex-wrap:wrap;padding:0 4px;">`;
    series.forEach(s => {
      html += `<div style="display:flex;align-items:center;gap:4px;font-size:11px;">
        <div style="width:12px;height:12px;background:${s.color || "#6b7280"};border-radius:2px;"></div>
        ${frappe.utils.escape_html(s.name)}
      </div>`;
    });
    html += `</div></div>`;
    $el.html(html);
  }

  // ── Agent Attribution table ────────────────────────────────────────────
  _renderAttribution(rows) {
    const $el = this.page.main.find(".sd-attribution").empty();
    if (!rows.length) {
      $el.html(`<div style="color:var(--text-muted);padding:8px">${__("No signed records in this period")}</div>`);
      return;
    }

    let html = `
      <div style="overflow:auto;max-height:320px;">
      <table class="table table-bordered" style="margin:0;font-size:12px;">
        <thead style="position:sticky;top:0;background:#f9fafb;">
          <tr>
            <th>${__("Agent")}</th>
            <th title="${__("Lead was theirs at sign time")}">${__("Lead Agent")}</th>
            <th title="${__("Manager assigned them commission")}">${__("Closer")}</th>
            <th title="${__("Closer - Lead Agent")}">Δ</th>
          </tr>
        </thead><tbody>`;

    rows.forEach(r => {
      const diff = r.diff || 0;
      const diffColor = diff > 0 ? "#10b981" : diff < 0 ? "#ef4444" : "var(--text-muted)";
      const diffStr = diff > 0 ? `+${diff}` : String(diff);
      html += `<tr>
        <td style="font-weight:500;">${frappe.utils.escape_html(r.display_name || r.agent)}</td>
        <td style="text-align:center;">${r.as_lead_agent}</td>
        <td style="text-align:center;font-weight:600;">${r.as_closing_agent}</td>
        <td style="text-align:center;color:${diffColor};font-weight:600;">${diffStr}</td>
      </tr>`;
    });

    html += `</tbody></table></div>
      <div style="font-size:11px;color:var(--text-muted);margin-top:6px;">
        ${__("Δ = Closer count minus Lead Agent count. Positive means agent closes more deals than they sourced.")}
      </div>`;
    $el.html(html);
  }

  // ── Pending Attribution table ──────────────────────────────────────────
  _renderPending(rows) {
    const $el = this.page.main.find(".sd-pending").empty();
    this.page.main.find(".sd-pending-badge").text(rows.length);

    if (!rows.length) {
      $el.html(`<div style="color:#10b981;padding:8px;font-weight:600;">
        ${frappe.utils.icon("check", "sm")} ${__("All Signs have a Closing Agent assigned. Nothing pending.")}
      </div>`);
      return;
    }

    let html = `<div style="overflow:auto;max-height:320px;">
      <table class="table table-bordered" style="margin:0;font-size:12px;">
        <thead style="position:sticky;top:0;background:#fff0f0;">
          <tr>
            <th>${__("Signs Record")}</th>
            <th>${__("Lead")}</th>
            <th>${__("Business")}</th>
            <th>${__("Lead Agent")}</th>
            <th>${__("Sign Date")}</th>
            <th>${__("Action")}</th>
          </tr>
        </thead><tbody>`;

    rows.forEach(r => {
      html += `<tr>
        <td><a href="/app/signs/${encodeURIComponent(r.name)}" target="_blank">${frappe.utils.escape_html(r.name)}</a></td>
        <td><a href="/app/atm-leads/${encodeURIComponent(r.atm_leads)}" target="_blank">${frappe.utils.escape_html(r.atm_leads || "")}</a></td>
        <td>${frappe.utils.escape_html(r.business_name || "")}</td>
        <td>${frappe.utils.escape_html(r.lead_agent || "—")}</td>
        <td>${frappe.utils.escape_html(r.sign_date || "")}</td>
        <td>
          <button class="btn btn-xs btn-warning sd-assign-btn"
                  data-signs="${frappe.utils.escape_html(r.name)}"
                  style="font-size:11px;">
            ${__("Assign Agent")}
          </button>
        </td>
      </tr>`;
    });

    html += `</tbody></table></div>`;
    $el.html(html);

    // Quick-assign click handler: open Signs record in dialog
    $el.find(".sd-assign-btn").on("click", (e) => {
      const name = $(e.currentTarget).data("signs");
      this._quickAssign(name);
    });
  }

  // ── Quick-assign closing agent dialog ─────────────────────────────────
  _quickAssign(signsName) {
    const d = new frappe.ui.Dialog({
      title: __("Assign Closing Agent — {0}", [signsName]),
      fields: [
        {
          label: __("Closing Agent (Commission)"),
          fieldtype: "Link",
          options: "Sales Agent",
          fieldname: "closing_agent",
          reqd: 1,
        },
        {
          label: __("Commission Notes"),
          fieldtype: "Small Text",
          fieldname: "closing_notes",
        },
      ],
      primary_action_label: __("Save"),
      primary_action: (values) => {
        frappe.call({
          method: "frappe.client.set_value",
          args: {
            doctype: "Signs",
            name: signsName,
            fieldname: {
              closing_agent: values.closing_agent,
              closing_notes: values.closing_notes || "",
            },
          },
          callback: () => {
            frappe.show_alert({ message: __("Closing agent assigned"), indicator: "green" });
            d.hide();
            this.refresh();
          },
        });
      },
    });
    d.show();
  }
}
