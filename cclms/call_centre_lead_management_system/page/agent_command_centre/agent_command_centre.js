frappe.pages["agent-command-centre"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Agent Command Centre"),
    single_column: true,
  });

  new cclms.AgentCommandCentre(page);
};

frappe.provide("cclms");

cclms.AgentCommandCentre = class {
  constructor(page) {
    this.page = page;
    this.limit = this.page.add_field({
      label: __("Rows"),
      fieldtype: "Int",
      fieldname: "limit",
      default: 20,
    });
    this.page.set_primary_action(__("Refresh"), () => this.refresh());
    this.make_layout();
    this.refresh();
  }

  make_layout() {
    this.page.main.html(`
      <div class="acc-wrap">
        <div class="acc-summary" style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;"></div>
        <div style="margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:12px;">
          <div class="acc-panel acc-notifications"></div>
          <div class="acc-panel acc-todos"></div>
        </div>
        <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:12px;">
          <div class="acc-panel acc-leads"></div>
          <div class="acc-panel acc-deals"></div>
        </div>
        <div style="margin-top:12px;">
          <div class="acc-panel acc-emails"></div>
        </div>
      </div>
    `);

    this.$summary = this.page.main.find(".acc-summary");
    this.$notifications = this.page.main.find(".acc-notifications");
    this.$todos = this.page.main.find(".acc-todos");
    this.$leads = this.page.main.find(".acc-leads");
    this.$deals = this.page.main.find(".acc-deals");
    this.$emails = this.page.main.find(".acc-emails");
  }

  async refresh() {
    const data = await frappe.call({
      method: "cclms.api.agent_command_centre.dashboard",
      args: { limit: this.limit.get_value() || 20 },
    }).then((r) => r.message || {});

    this.render_summary(data.summary || {});
    this.render_notifications(data.notifications || []);
    this.render_todos(data.todos || []);
    this.render_leads(data.lead_actions || []);
    this.render_deals(data.deal_actions || []);
    this.render_emails(data.emails || []);
  }

  render_summary(summary) {
    const items = [
      ["Notifications", summary.notifications || 0],
      ["ToDos", summary.todos || 0],
      ["Lead Actions", summary.lead_actions || 0],
      ["Deal Actions", summary.deal_actions || 0],
      ["Emails", summary.emails || 0],
    ];

    this.$summary.empty();
    items.forEach(([label, value]) => {
      this.$summary.append(`
        <div style="border:1px solid var(--border-color);border-radius:10px;padding:12px;">
          <div style="font-size:12px;color:var(--text-muted);">${frappe.utils.escape_html(label)}</div>
          <div style="font-size:28px;font-weight:700;">${value}</div>
        </div>
      `);
    });
  }

  render_notifications(rows) {
    this.$notifications.html(this.render_table_panel(
      __("System Notifications"),
      rows,
      [
        { key: "subject", label: __("Subject") },
        { key: "document_type", label: __("DocType") },
        { key: "document_name", label: __("Document"), link: (row) => this.doc_link(row.document_type, row.document_name) },
        { key: "creation", label: __("Created") },
      ]
    ));
  }

  render_todos(rows) {
    this.$todos.html(this.render_table_panel(
      __("Pending ToDos"),
      rows,
      [
        { key: "description", label: __("Task") },
        { key: "priority", label: __("Priority") },
        { key: "reference_name", label: __("Reference"), link: (row) => this.doc_link(row.reference_type, row.reference_name) },
        { key: "date", label: __("Date") },
      ]
    ));
  }

  render_leads(rows) {
    this.$leads.html(this.render_table_panel(
      __("ATM Lead Actions"),
      rows,
      [
        { key: "business_name", label: __("Business") },
        { key: "workflow_state", label: __("Stage") },
        { key: "required_role", label: __("Role") },
        { key: "name", label: __("Lead"), link: (row) => this.doc_link("ATM Leads", row.name) },
      ]
    ));
  }

  render_deals(rows) {
    this.$deals.html(this.render_table_panel(
      __("Operator Deal Actions"),
      rows,
      [
        { key: "name", label: __("Deal"), link: (row) => this.doc_link("Operator Deal", row.name) },
        { key: "status", label: __("Status") },
        { key: "operator_company", label: __("Operator") },
        { key: "modified", label: __("Updated") },
      ]
    ));
  }

  render_emails(rows) {
    this.$emails.html(this.render_table_panel(
      __("Operations Inbox"),
      rows,
      [
        { key: "subject", label: __("Subject"), link: (row) => this.doc_link("Communication", row.name) },
        { key: "sender_full_name", label: __("Sender"), fallback: "sender" },
        { key: "email_account", label: __("Inbox") },
        { key: "creation", label: __("Received") },
      ]
    ));
  }

  render_table_panel(title, rows, columns) {
    let html = `<div style="border:1px solid var(--border-color);border-radius:10px;padding:10px;">`;
    html += `<h5 style="margin:4px 4px 10px 4px;">${frappe.utils.escape_html(title)}</h5>`;
    html += `<div style="overflow:auto;"><table class="table table-bordered" style="margin:0;">`;
    html += `<thead><tr>${columns.map((col) => `<th>${frappe.utils.escape_html(col.label)}</th>`).join("")}</tr></thead><tbody>`;

    if (!rows.length) {
      html += `<tr><td colspan="${columns.length}" class="text-muted">${__("No items right now")}</td></tr>`;
    } else {
      rows.forEach((row) => {
        html += "<tr>";
        columns.forEach((col) => {
          const raw = row[col.key] || row[col.fallback] || "";
          const text = frappe.utils.escape_html(String(raw));
          const href = col.link ? col.link(row) : null;
          html += `<td>${href ? `<a href="${href}">${text || __("Open")}</a>` : text}</td>`;
        });
        html += "</tr>";
      });
    }

    html += "</tbody></table></div></div>";
    return html;
  }

  doc_link(doctype, name) {
    if (!doctype || !name) {
      return "";
    }
    return `/app/${this.slugify(doctype)}/${encodeURIComponent(name)}`;
  }

  slugify(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "-");
  }
};
