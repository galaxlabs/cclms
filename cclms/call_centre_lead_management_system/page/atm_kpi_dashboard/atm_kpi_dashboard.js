frappe.provide("cclms");

frappe.pages["atm-kpi-dashboard"].on_page_load = function (wrapper) {
    wrapper.atm_kpi_dashboard = new cclms.ATM_KPI_Dashboard(wrapper);
};

cclms.ATM_KPI_Dashboard = class {
    constructor(wrapper) {
        this.wrapper = $(wrapper).empty();
        this.make_layout();
        this.setup_filters();
        this.load_data();
    }

	make_layout() {
    this.wrapper.append(`
        <div class="atm-kpi-dashboard" style="padding: 15px;">
            <div class="atm-kpi-filters row" style="margin-bottom: 15px;">
                <div class="col-md-4 filters-left"></div>
                <div class="col-md-6 filters-middle"></div>
                <div class="col-md-2 text-right filters-right">
                    <button class="btn btn-primary btn-sm atm-kpi-refresh">
                        ${__("Refresh")}
                    </button>
                </div>
            </div>

            <div class="atm-kpi-summary row" style="margin-bottom: 12px;"></div>

            <div class="atm-kpi-chart" style="margin-bottom: 15px;"></div>

            <div class="atm-kpi-table" style="margin-bottom: 18px;"></div>

            <div class="atm-kpi-company-table" style="margin-bottom: 18px;"></div>

            <div class="atm-kpi-company-agent-table"></div>
        </div>
    `);

    this.$filters = this.wrapper.find(".atm-kpi-filters");
    this.$summary = this.wrapper.find(".atm-kpi-summary");
    this.$chart = this.wrapper.find(".atm-kpi-chart");
    this.$table = this.wrapper.find(".atm-kpi-table");
    this.$company_table = this.wrapper.find(".atm-kpi-company-table");
    this.$company_agent_table = this.wrapper.find(".atm-kpi-company-agent-table");
    this.$refresh_btn = this.wrapper.find(".atm-kpi-refresh");
}

    setup_filters() {
        const me = this;

        // Time Span select
        this.timespan_control = frappe.ui.form.make_control({
            parent: this.$filters.find(".filters-left"),
            df: {
                fieldtype: "Select",
                fieldname: "timespan",
                label: __("Time Span"),
                options: "This Week\nThis Month\nCustom",
                default: "This Week",
            },
            render_input: true,
        });

        // From Date
        this.from_date_control = frappe.ui.form.make_control({
            parent: this.$filters.find(".filters-middle"),
            df: {
                fieldtype: "Date",
                fieldname: "from_date",
                label: __("From Date"),
                default: frappe.datetime.get_today(),
            },
            render_input: true,
        });

        // To Date
        this.to_date_control = frappe.ui.form.make_control({
            parent: this.$filters.find(".filters-middle"),
            df: {
                fieldtype: "Date",
                fieldname: "to_date",
                label: __("To Date"),
                default: frappe.datetime.get_today(),
            },
            render_input: true,
        });

        // align date controls side by side
        this.$filters.find(".filters-middle .frappe-control").addClass("mr-2").css("display", "inline-block");

        const toggle_date_visibility = () => {
            const ts = me.timespan_control.get_value();
            const show_custom = ts === "Custom";
            const $from = $(me.from_date_control.$wrapper);
            const $to = $(me.to_date_control.$wrapper);
            if (show_custom) {
                $from.show();
                $to.show();
            } else {
                $from.hide();
                $to.hide();
            }
        };

        toggle_date_visibility();

        // Timespan change -> hide/show dates + reload
        this.timespan_control.$input.on("change", () => {
            toggle_date_visibility();
            me.load_data();
        });

        // Refresh button
        this.$refresh_btn.on("click", () => {
            me.load_data();
        });
    }

    get_filters() {
        return {
            timespan: this.timespan_control.get_value(),
            from_date: this.from_date_control.get_value(),
            to_date: this.to_date_control.get_value(),
        };
    }

	load_data() {
    const me = this;
    const filters = this.get_filters();

    // 1) Agent-wise KPI (scripted report)
    frappe.call({
        method: "frappe.desk.query_report.run",
        args: {
            report_name: "Weekly ATM KPI",
            filters: filters,
            ignore_prepared_report: true,
        },
        freeze: true,
        freeze_message: __("Loading ATM KPI..."),
    }).then((r) => {
        const msg = r.message || {};
        const columns = msg.columns || [];
        const result = msg.result || [];
        const summary = msg.report_summary || [];
        const chart = msg.chart || null;

        me.render_summary(summary, result);
        me.render_chart(chart);
        me.render_table(columns, result);

        // 2) Company-wise summary
        return frappe.call({
            method: "cclms.call_centre_lead_management_system.page.atm_kpi_dashboard.atm_kpi_dashboard.get_company_breakdown",
            args: filters,
        });
    }).then((r2) => {
        const info = (r2 && r2.message) || {};
        me.render_company_table(info);

        // 3) Signed matrix (Agent × Company)
        return frappe.call({
            method: "cclms.call_centre_lead_management_system.page.atm_kpi_dashboard.atm_kpi_dashboard.get_signed_matrix",
            args: filters,
        });
    }).then((r3) => {
        const info2 = (r3 && r3.message) || {};
        me.render_company_agent_matrix(info2);
    });
}


    // -----------------------------
    // SUMMARY CARDS (with extra Signed + Installed)
    // -----------------------------
    render_summary(summary, rows) {
        this.$summary.empty();

        let items = summary ? summary.slice() : [];

        // Compute total signed & installed from agent rows
        let total_signed = 0;
        let total_installed = 0;
        (rows || []).forEach(r => {
            total_signed += r.signed || 0;
            total_installed += r.installed || 0;
        });

        items.push({
            label: __("Total Signed"),
            value: total_signed,
            indicator: total_signed > 0 ? "Green" : "Red",
            datatype: "Int",
            _accent: "signed"
        });

        items.push({
            label: __("Total Installed"),
            value: total_installed,
            indicator: total_installed > 0 ? "Green" : "Red",
            datatype: "Int",
            _accent: "installed"
        });

        if (!items.length) return;

        items.forEach((item) => {
            const indicator = (item.indicator || "Blue").toLowerCase();
            let bg = "#f3f4f6"; // default

            if (indicator === "green") bg = "#dcfce7";
            if (indicator === "red") bg = "#fee2e2";
            if (indicator === "orange") bg = "#ffedd5";
            if (indicator === "blue") bg = "#dbeafe";

            // stronger accent for special cards
            if (item._accent === "signed") {
                bg = "linear-gradient(135deg, #22c55e, #16a34a)";
            }
            if (item._accent === "installed") {
                bg = "linear-gradient(135deg, #6366f1, #4f46e5)";
            }

            const text_color = (item._accent === "signed" || item._accent === "installed") ? "#ffffff" : "#111827";

            const raw_val = item.value;
            const display_val =
                item.datatype === "Percent"
                    ? `${flt(raw_val, 2)}%`
                    : raw_val;

            const card = $(`
                <div class="col-md-3" style="margin-bottom: 10px;">
                    <div class="card shadow-sm"
                         style="background:${bg}; border:0; border-radius:10px; padding:8px; min-height:76px;">
                        <div class="card-body" style="padding:6px 10px;">
                            <div style="font-size:11px; text-transform:uppercase; opacity:0.85; color:${text_color};">
                                ${frappe.utils.escape_html(item.label || "")}
                            </div>
                            <div style="font-size:18px; font-weight:600; color:${text_color}; margin-top:2px;">
                                ${frappe.utils.escape_html(String(display_val))}
                            </div>
                        </div>
                    </div>
                </div>
            `);

            this.$summary.append(card);
        });
    }

    // -----------------------------
    // CHART
    // -----------------------------
    render_chart(chart_cfg) {
        this.$chart.empty();

        if (!chart_cfg || !chart_cfg.data || !chart_cfg.data.labels) {
            return;
        }

        const $chart_container = $(
            `<div style="background:#ffffff; border-radius:8px; padding:10px; box-shadow:0 1px 3px rgba(15,23,42,0.08);">
                <div style="font-weight:600; margin-bottom:6px;">
                    ${__("Created vs Approved (by Pseudo Name)")}
                </div>
                <div class="atm-kpi-chart-inner"></div>
            </div>`
        );
        this.$chart.append($chart_container);

        const chart_data = chart_cfg.data;
        const type = chart_cfg.type || "bar";

        new frappe.Chart($chart_container.find(".atm-kpi-chart-inner")[0], {
            data: chart_data,
            type: type,
            height: 240,
        });
    }

    // -----------------------------
    // AGENT TABLE
    // -----------------------------
    render_table(columns, rows) {
        this.$table.empty();

        if (!rows || !rows.length) {
            this.$table.append(
                `<div class="text-muted" style="margin-top:10px;">${__(
                    "No data for selected period."
                )}</div>`
            );
            return;
        }

        const cols = [
            { fieldname: "pseudo_name", label: __("Pseudo Name") },
            { fieldname: "official_name", label: __("Official Name") },
            { fieldname: "created", label: __("Created") },
            { fieldname: "approved", label: __("Approved") },
            { fieldname: "rejected", label: __("Rejected") },
            { fieldname: "signed", label: __("Signed") },
            { fieldname: "converted", label: __("Converted") },
            { fieldname: "installed", label: __("Installed") },
            { fieldname: "sign_rejected", label: __("Sign Rejected") },
            { fieldname: "ratio_approved_created", label: __("Approved / Created %") },
            { fieldname: "ratio_rejected_created", label: __("Rejected / Created %") },
            { fieldname: "ratio_signed_approved", label: __("Signed / Approved %") },
            { fieldname: "ratio_converted_signed", label: __("Converted / Signed %") },
            { fieldname: "ratio_installed_signed", label: __("Installed / Signed %") },
            { fieldname: "ratio_sign_rejected_signed", label: __("Sign Rejected / Signed %") },
            { fieldname: "monthly_ratio_approved_created", label: __("Approved / Created (Month) %") },
        ];

        const $table = $(`
            <div style="background:#ffffff; border-radius:8px; padding:10px; box-shadow:0 1px 3px rgba(15,23,42,0.06);">
                <div style="font-weight:600; margin-bottom:6px;">
                    ${__("Agent-wise KPI Details")}
                </div>
                <div class="table-responsive">
                    <table class="table table-bordered table-sm atm-kpi-table-inner">
                        <thead></thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        `);

        const $thead = $table.find("thead");
        const $tbody = $table.find("tbody");

        let header_html = `
            <tr style="background:#111827; color:#f9fafb;">
        `;
        cols.forEach((c) => {
            header_html += `<th style="white-space:nowrap; font-weight:600;">${frappe.utils.escape_html(
                c.label
            )}</th>`;
        });
        header_html += "</tr>";
        $thead.html(header_html);

        rows.forEach((r) => {
            let tr = "<tr>";
            cols.forEach((c) => {
                let val = r[c.fieldname];

                // numeric ratios
                if (c.fieldname.startsWith("ratio_") || c.fieldname === "monthly_ratio_approved_created") {
                    const num = flt(val, 2);
                    const color = this.get_ratio_color(num, c.fieldname);
                    const display = `${num}%`;
                    tr += `<td style="font-weight:bold; color:${color}; text-align:right;">${display}</td>`;
                    return;
                }

                // pseudo name highlight
                if (c.fieldname === "pseudo_name") {
                    val = val || "";
                    tr += `<td style="font-weight:bold;">${frappe.utils.escape_html(
                        String(val)
                    )}</td>`;
                    return;
                }

                // official name
                if (c.fieldname === "official_name") {
                    val = val || "";
                    tr += `<td>${frappe.utils.escape_html(String(val))}</td>`;
                    return;
                }

                // integers
                if (["created","approved","rejected","signed","converted","installed","sign_rejected"].includes(c.fieldname)) {
                    const num = val || 0;
                    tr += `<td style="text-align:right;">${num}</td>`;
                    return;
                }

                // fallback
                val = val == null ? "" : val;
                tr += `<td>${frappe.utils.escape_html(String(val))}</td>`;
            });
            tr += "</tr>";
            $tbody.append(tr);
        });

        this.$table.append($table);
    }

    // -----------------------------
    // COMPANY TABLE (group by company)
    // -----------------------------
    render_company_table(info) {
        this.$company_table.empty();

        const rows = (info && info.rows) || [];
        const totals = (info && info.totals) || {};

        const title = __("Company-wise KPI Summary");

        if (!rows.length) {
            this.$company_table.append(
                `<div class="text-muted" style="margin-top:4px;">${__(
                    "No company data for selected period."
                )}</div>`
            );
            return;
        }

        const $wrap = $(`
            <div style="background:#ffffff; border-radius:8px; padding:10px; box-shadow:0 1px 4px rgba(15,23,42,0.08);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <div style="font-weight:600;">${title}</div>
                    <div style="font-size:11px; color:#6b7280;">
                        ${__("Companies")}: ${totals.companies || 0}
                        &nbsp;•&nbsp;
                        ${__("Agents")}: ${totals.agent_count || 0}
                    </div>
                </div>
                <div class="table-responsive">
                    <table class="table table-bordered table-sm atm-kpi-company-inner">
                        <thead></thead>
                        <tbody></tbody>
                        <tfoot></tfoot>
                    </table>
                </div>
            </div>
        `);

        const $thead = $wrap.find("thead");
        const $tbody = $wrap.find("tbody");
        const $tfoot = $wrap.find("tfoot");

        const header = `
            <tr style="background:linear-gradient(135deg,#0f172a,#1f2937); color:#f9fafb;">
                <th>${__("Company")}</th>
                <th class="text-right">${__("# Agents")}</th>
                <th class="text-right">${__("Created")}</th>
                <th class="text-right">${__("Approved")}</th>
                <th class="text-right">${__("Rejected")}</th>
                <th class="text-right">${__("Signed")}</th>
                <th class="text-right">${__("Converted")}</th>
                <th class="text-right">${__("Installed")}</th>
                <th class="text-right">${__("Sign Rejected")}</th>
            </tr>
        `;
        $thead.html(header);

        rows.forEach((r) => {
            const tr = $(`
                <tr>
                    <td>${frappe.utils.escape_html(r.company || "")}</td>
                    <td class="text-right">${r.agent_count || 0}</td>
                    <td class="text-right">${r.created || 0}</td>
                    <td class="text-right">${r.approved || 0}</td>
                    <td class="text-right">${r.rejected || 0}</td>
                    <td class="text-right">${r.signed || 0}</td>
                    <td class="text-right">${r.converted || 0}</td>
                    <td class="text-right">${r.installed || 0}</td>
                    <td class="text-right">${r.sign_rejected || 0}</td>
                </tr>
            `);
            $tbody.append(tr);
        });

        // footer totals
        const ft = $(`
            <tr style="font-weight:600; background:#f9fafb;">
                <td>${__("TOTAL")}</td>
                <td class="text-right">${totals.agent_count || 0}</td>
                <td class="text-right">${totals.created || 0}</td>
                <td class="text-right">${totals.approved || 0}</td>
                <td class="text-right">${totals.rejected || 0}</td>
                <td class="text-right">${totals.signed || 0}</td>
                <td class="text-right">${totals.converted || 0}</td>
                <td class="text-right">${totals.installed || 0}</td>
                <td class="text-right">${totals.sign_rejected || 0}</td>
            </tr>
        `);
        $tfoot.append(ft);

        this.$company_table.append($wrap);
    }

	// -----------------------------
// COMPANY × AGENT SIGNED MATRIX  (like your Excel screenshot)
// -----------------------------
render_company_agent_matrix(info) {
    this.$company_agent_table.empty();

    const companies = (info && info.companies) || [];
    const agents = (info && info.agents) || [];
    const totals = (info && info.totals) || { signed_total: 0, per_company: {} };

    if (!agents.length) {
        this.$company_agent_table.append(
            `<div class="text-muted" style="margin-top:6px;">${__(
                "No signed leads for selected period."
            )}</div>`
        );
        return;
    }

    const $wrap = $(`
        <div style="border-radius:8px; overflow:hidden; box-shadow:0 1px 5px rgba(15,23,42,0.25); margin-top:10px;">
            <div style="padding:6px 10px; background:#b91c1c; color:#f9fafb; font-weight:600; text-transform:uppercase; letter-spacing:0.03em;">
                ${__("Signed Deals Matrix (Agent × Company)")}
            </div>
            <div class="table-responsive" style="background:#111827;">
                <table class="table table-sm mb-0" style="color:#f9fafb;">
                    <thead></thead>
                    <tbody></tbody>
                    <tfoot></tfoot>
                </table>
            </div>
        </div>
    `);

    const $thead = $wrap.find("thead");
    const $tbody = $wrap.find("tbody");
    const $tfoot = $wrap.find("tfoot");

    // Header row – red style like Excel
    let h = `
        <tr style="background:#ef4444; color:#111827; font-weight:600;">
            <th>${__("Executive Name")}</th>
            <th>${__("Pseudo Name")}</th>
            <th class="text-right">${__("Signed")}</th>
    `;
    companies.forEach((c) => {
        h += `<th class="text-right">${frappe.utils.escape_html(c)}</th>`;
    });
    h += `
            <th class="text-right">${__("KPI Min")}</th>
            <th class="text-right">${__("KPI Max")}</th>
        </tr>
    `;
    $thead.html(h);

    // Body rows (one per agent)
    agents.forEach((a) => {
        let tr = `
            <tr style="background:#1f2937;">
                <td>${frappe.utils.escape_html(a.official_name || a.executive_name || "")}</td>
                <td>${frappe.utils.escape_html(a.pseudo_name || "")}</td>
                <td class="text-right">${a.signed_total || 0}</td>
        `;

        companies.forEach((c) => {
            const val = (a.per_company && a.per_company[c]) || 0;
            tr += `<td class="text-right">${val}</td>`;
        });

        tr += `
                <td class="text-right">${a.kpi_min != null ? a.kpi_min : ""}</td>
                <td class="text-right">${a.kpi_max != null ? a.kpi_max : ""}</td>
            </tr>
        `;
        $tbody.append(tr);
    });

    // Footer total row – bottom "Total" like Excel
    let ft = `
        <tr style="background:#b91c1c; color:#f9fafb; font-weight:600;">
            <td>${__("Total")}</td>
            <td></td>
            <td class="text-right">${totals.signed_total || 0}</td>
    `;
    companies.forEach((c) => {
        const tv = (totals.per_company && totals.per_company[c]) || 0;
        ft += `<td class="text-right">${tv}</td>`;
    });
    ft += `
            <td></td>
            <td></td>
        </tr>
    `;
    $tfoot.html(ft);

    this.$company_agent_table.append($wrap);
}


    // -----------------------------
    // Ratio colour helper
    // -----------------------------
    get_ratio_color(value, fieldname) {
        let ratio = value || 0;

        // rejection ratios: lower is better
        if (["ratio_rejected_created", "ratio_sign_rejected_signed"].includes(fieldname)) {
            if (ratio <= 10) return "green";
            if (ratio <= 30) return "orange";
            return "red";
        }

        // normal ratios: higher is better
        if (ratio >= 70) return "green";
        if (ratio >= 40) return "orange";
        return "red";
    }
};

// frappe.provide("cclms");

// frappe.pages["atm-kpi-dashboard"].on_page_load = function (wrapper) {
//     wrapper.atm_kpi_dashboard = new cclms.ATM_KPI_Dashboard(wrapper);
// };

// cclms.ATM_KPI_Dashboard = class {
//     constructor(wrapper) {
//         this.wrapper = $(wrapper).empty();
//         this.make_layout();
//         this.setup_filters();
//         this.load_data();
//     }

//     make_layout() {
//         this.wrapper.append(`
//             <div class="atm-kpi-dashboard" style="padding: 15px;">
//                 <div class="atm-kpi-filters row" style="margin-bottom: 15px;">
//                     <div class="col-md-4 filters-left"></div>
//                     <div class="col-md-6 filters-middle"></div>
//                     <div class="col-md-2 text-right filters-right">
//                         <button class="btn btn-primary btn-sm atm-kpi-refresh">
//                             ${__("Refresh")}
//                         </button>
//                     </div>
//                 </div>

//                 <div class="atm-kpi-summary row" style="margin-bottom: 10px;"></div>

//                 <div class="atm-kpi-chart" style="margin-bottom: 15px;"></div>

//                 <div class="atm-kpi-table"></div>
//             </div>
//         `);

//         this.$filters = this.wrapper.find(".atm-kpi-filters");
//         this.$summary = this.wrapper.find(".atm-kpi-summary");
//         this.$chart = this.wrapper.find(".atm-kpi-chart");
//         this.$table = this.wrapper.find(".atm-kpi-table");

//         this.$refresh_btn = this.wrapper.find(".atm-kpi-refresh");
//     }

//     setup_filters() {
//         const me = this;

//         // Time Span select
//         this.timespan_control = frappe.ui.form.make_control({
//             parent: this.$filters.find(".filters-left"),
//             df: {
//                 fieldtype: "Select",
//                 fieldname: "timespan",
//                 label: __("Time Span"),
//                 options: "This Week\nThis Month\nCustom",
//                 default: "This Week",
//             },
//             render_input: true,
//         });

//         // From Date
//         this.from_date_control = frappe.ui.form.make_control({
//             parent: this.$filters.find(".filters-middle"),
//             df: {
//                 fieldtype: "Date",
//                 fieldname: "from_date",
//                 label: __("From Date"),
//                 default: frappe.datetime.get_today(),
//             },
//             render_input: true,
//         });

//         // To Date
//         this.to_date_control = frappe.ui.form.make_control({
//             parent: this.$filters.find(".filters-middle"),
//             df: {
//                 fieldtype: "Date",
//                 fieldname: "to_date",
//                 label: __("To Date"),
//                 default: frappe.datetime.get_today(),
//             },
//             render_input: true,
//         });

//         // align date controls side by side
//         this.$filters.find(".filters-middle .frappe-control").addClass("mr-2").css("display", "inline-block");

//         const toggle_date_visibility = () => {
//             const ts = me.timespan_control.get_value();
//             const show_custom = ts === "Custom";
//             const $from = $(me.from_date_control.$wrapper);
//             const $to = $(me.to_date_control.$wrapper);
//             if (show_custom) {
//                 $from.show();
//                 $to.show();
//             } else {
//                 $from.hide();
//                 $to.hide();
//             }
//         };

//         toggle_date_visibility();

//         // Timespan change -> hide/show dates + reload
//         this.timespan_control.$input.on("change", () => {
//             toggle_date_visibility();
//             me.load_data();
//         });

//         // Refresh button
//         this.$refresh_btn.on("click", () => {
//             me.load_data();
//         });
//     }

//     get_filters() {
//         return {
//             timespan: this.timespan_control.get_value(),
//             from_date: this.from_date_control.get_value(),
//             to_date: this.to_date_control.get_value(),
//         };
//     }

//     load_data() {
//         const me = this;
//         const filters = this.get_filters();

//         frappe.call({
//             method: "frappe.desk.query_report.run",
//             args: {
//                 report_name: "Weekly ATM KPI", // scripted report we made
//                 filters: filters,
//                 ignore_prepared_report: true,
//             },
//             freeze: true,
//             freeze_message: __("Loading ATM KPI..."),
//         }).then((r) => {
//             const msg = r.message || {};
//             const columns = msg.columns || [];
//             const result = msg.result || [];
//             const summary = msg.report_summary || [];
//             const chart = msg.chart || null;

//             me.render_summary(summary);
//             me.render_chart(chart);
//             me.render_table(columns, result);
//         });
//     }

//     render_summary(summary) {
//         this.$summary.empty();

//         if (!summary || !summary.length) {
//             return;
//         }

//         summary.forEach((item) => {
//             const indicator = (item.indicator || "Blue").toLowerCase();
//             let bg = "#eef2f7";
//             if (indicator === "green") bg = "#e6ffed";
//             if (indicator === "red") bg = "#ffe6e6";
//             if (indicator === "orange") bg = "#fff4e6";
//             if (indicator === "blue") bg = "#e6f0ff";

//             const value =
//                 item.datatype === "Percent"
//                     ? `${flt(item.value, 2)}%`
//                     : item.value;

//             const card = $(`
//                 <div class="col-md-3" style="margin-bottom: 8px;">
//                     <div class="card" style="background:${bg}; padding:8px; min-height:70px;">
//                         <div class="card-body" style="padding:4px 8px;">
//                             <div style="font-size:11px; text-transform:uppercase; opacity:0.8;">
//                                 ${frappe.utils.escape_html(item.label || "")}
//                             </div>
//                             <div style="font-size:16px; font-weight:bold;">
//                                 ${frappe.utils.escape_html(String(value))}
//                             </div>
//                         </div>
//                     </div>
//                 </div>
//             `);

//             this.$summary.append(card);
//         });
//     }

//     render_chart(chart_cfg) {
//         this.$chart.empty();

//         if (!chart_cfg || !chart_cfg.data || !chart_cfg.data.labels) {
//             return;
//         }

//         const $chart_container = $(
//             `<div style="background:#fff; border-radius:4px; padding:10px;">
//                 <div style="font-weight:bold; margin-bottom:5px;">
//                     ${__("Created vs Approved (by Pseudo Name)")}
//                 </div>
//                 <div class="atm-kpi-chart-inner"></div>
//             </div>`
//         );
//         this.$chart.append($chart_container);

//         const chart_data = chart_cfg.data;
//         const type = chart_cfg.type || "bar";

//         new frappe.Chart($chart_container.find(".atm-kpi-chart-inner")[0], {
//             data: chart_data,
//             type: type,
//             height: 240,
//         });
//     }

//     render_table(columns, rows) {
//         this.$table.empty();

//         if (!rows || !rows.length) {
//             this.$table.append(
//                 `<div class="text-muted" style="margin-top:10px;">${__(
//                     "No data for selected period."
//                 )}</div>`
//             );
//             return;
//         }

//         // We'll ignore "columns" from report and define our own order
//         const cols = [
//             { fieldname: "pseudo_name", label: __("Pseudo Name") },
//             { fieldname: "official_name", label: __("Official Name") },
//             { fieldname: "created", label: __("Created") },
//             { fieldname: "approved", label: __("Approved") },
//             { fieldname: "rejected", label: __("Rejected") },
//             { fieldname: "signed", label: __("Signed") },
//             { fieldname: "converted", label: __("Converted") },
//             { fieldname: "installed", label: __("Installed") },
//             { fieldname: "sign_rejected", label: __("Sign Rejected") },
//             { fieldname: "ratio_approved_created", label: __("Approved / Created %") },
//             { fieldname: "ratio_rejected_created", label: __("Rejected / Created %") },
//             { fieldname: "ratio_signed_approved", label: __("Signed / Approved %") },
//             { fieldname: "ratio_converted_signed", label: __("Converted / Signed %") },
//             { fieldname: "ratio_installed_signed", label: __("Installed / Signed %") },
//             { fieldname: "ratio_sign_rejected_signed", label: __("Sign Rejected / Signed %") },
//             { fieldname: "monthly_ratio_approved_created", label: __("Approved / Created (Month) %") },
//         ];

//         const $table = $(`
//             <div style="background:#fff; border-radius:4px; padding:8px;">
//                 <div style="font-weight:bold; margin-bottom:5px;">
//                     ${__("Agent-wise KPI Details")}
//                 </div>
//                 <div class="table-responsive">
//                     <table class="table table-bordered table-sm atm-kpi-table-inner">
//                         <thead></thead>
//                         <tbody></tbody>
//                     </table>
//                 </div>
//             </div>
//         `);

//         const $thead = $table.find("thead");
//         const $tbody = $table.find("tbody");

//         // header
//         let header_html = "<tr>";
//         cols.forEach((c) => {
//             header_html += `<th style="white-space:nowrap;">${frappe.utils.escape_html(
//                 c.label
//             )}</th>`;
//         });
//         header_html += "</tr>";
//         $thead.html(header_html);

//         // rows
//         rows.forEach((r) => {
//             let tr = "<tr>";
//             cols.forEach((c) => {
//                 let val = r[c.fieldname];

//                 // numeric ratios
//                 if (c.fieldname.startsWith("ratio_") || c.fieldname === "monthly_ratio_approved_created") {
//                     const num = flt(val, 2);
//                     const color = this.get_ratio_color(num, c.fieldname);
//                     const display = `${num}%`;
//                     tr += `<td style="font-weight:bold; color:${color}; text-align:right;">${display}</td>`;
//                     return;
//                 }

//                 // pseudo name highlight
//                 if (c.fieldname === "pseudo_name") {
//                     val = val || "";
//                     tr += `<td style="font-weight:bold;">${frappe.utils.escape_html(
//                         String(val)
//                     )}</td>`;
//                     return;
//                 }

//                 // official name normal
//                 if (c.fieldname === "official_name") {
//                     val = val || "";
//                     tr += `<td>${frappe.utils.escape_html(String(val))}</td>`;
//                     return;
//                 }

//                 // integers
//                 if (["created","approved","rejected","signed","converted","installed","sign_rejected"].includes(c.fieldname)) {
//                     const num = val || 0;
//                     tr += `<td style="text-align:right;">${num}</td>`;
//                     return;
//                 }

//                 // fallback
//                 val = val == null ? "" : val;
//                 tr += `<td>${frappe.utils.escape_html(String(val))}</td>`;
//             });
//             tr += "</tr>";
//             $tbody.append(tr);
//         });

//         this.$table.append($table);
//     }

//     get_ratio_color(value, fieldname) {
//         // value is already %
//         let ratio = value || 0;

//         // rejection ratios: lower is better
//         if (["ratio_rejected_created", "ratio_sign_rejected_signed"].includes(fieldname)) {
//             if (ratio <= 10) return "green";
//             if (ratio <= 30) return "orange";
//             return "red";
//         }

//         // normal ratios: higher is better
//         if (ratio >= 70) return "green";
//         if (ratio >= 40) return "orange";
//         return "red";
//     }
// };

// // frappe.pages['atm-kpi-dashboard'].on_page_load = function(wrapper) {
// // 	var page = frappe.ui.make_app_page({
// // 		parent: wrapper,
// // 		title: 'ATM KPI Dashboard',
// // 		single_column: true
// // 	});
// // }
// window.cclms = window.cclms || {};

// frappe.pages['atm-kpi-dashboard'].on_page_load = function (wrapper) {
//     const page = frappe.ui.make_app_page({
//         parent: wrapper,
//         title: __('ATM KPI Dashboard'),
//         single_column: true
//     });

//     new cclms.ATMKPIDashboard(page);
// };

// cclms.ATMKPIDashboard = class ATMKPIDashboard {
//     constructor(page) {
//         this.page = page;
//         this.make_filters();
//         this.make_container();
//         this.refresh();
//     }

//     make_filters() {
//         const me = this;
//         const today = new Date();
//         const current_year = today.getFullYear();
//         const current_month = (today.getMonth() + 1).toString().padStart(2, '0');

//         this.year_field = this.page.add_field({
//             fieldname: 'year',
//             label: __('Year'),
//             fieldtype: 'Int',
//             default: current_year
//         });

//         this.month_field = this.page.add_field({
//             fieldname: 'month',
//             label: __('Month'),
//             fieldtype: 'Select',
//             options: '01\n02\n03\n04\n05\n06\n07\n08\n09\n10\n11\n12',
//             default: current_month
//         });

//         this.page.set_primary_action(__('Refresh'), function () {
//             me.refresh();
//         });
//     }

//     make_container() {
//         this.$body = $(this.page.body);
//         this.$body.empty();

//         this.$summary = $(`
//             <div style="margin-bottom: 10px;">
//                 <h4 class="text-muted"></h4>
//             </div>
//         `).appendTo(this.$body);

//         this.$table_wrapper = $(`
//             <div class="kpi-table-wrapper">
//                 <table class="table table-bordered table-sm">
//                     <thead></thead>
//                     <tbody></tbody>
//                     <tfoot></tfoot>
//                 </table>
//             </div>
//         `).appendTo(this.$body);

//         this.$thead = this.$table_wrapper.find('thead');
//         this.$tbody = this.$table_wrapper.find('tbody');
//         this.$tfoot = this.$table_wrapper.find('tfoot');
//     }

//     refresh() {
//         const me = this;
//         const year = this.year_field.get_value();
//         const month = this.month_field.get_value();

//         frappe.call({
//             method: 'cclms.call_centre_lead_management_system.page.atm_kpi_dashboard.atm_kpi_dashboard.get_dashboard_data',
//             args: { year, month },
//             freeze: true,
//             freeze_message: __('Loading KPI data...'),
//             callback(r) {
//                 if (!r.message) {
//                     frappe.msgprint(__('No data returned'));
//                     return;
//                 }
//                 me.render(r.message);
//             }
//         });
//     }

//     render(data) {
//         const companies = data.companies || [];
//         const agents = data.agents || [];
//         const totals = data.totals || { per_company: {}, signed_total: 0 };

//         this.$summary.find('h4').text(
//             `Month: ${data.month}-${data.year} | Agents: ${agents.length}`
//         );

//         this.$thead.empty();
//         const $hr = $('<tr></tr>');
//         $hr.append(`<th>${__('Executive Name')}</th>`);
// 		// $hr.append(`<th>${__('Pseudo Name')}</th>`);
//         $hr.append(`<th>${__('Signed Total')}</th>`);
//         companies.forEach(c => {
//             $hr.append(`<th>${frappe.utils.escape_html(c)}</th>`);
//         });
//         $hr.append(`<th>${__('KPI Min')}</th>`);
//         $hr.append(`<th>${__('KPI Max')}</th>`);
//         this.$thead.append($hr);

//         this.$tbody.empty();

//         agents.forEach(a => {
//             const per_company = a.per_company || {};
//             const $row = $('<tr></tr>');

//             const label = a.full_name || a.executive_name;
//             $row.append(`<td>${frappe.utils.escape_html(label)}</td>`);
//             $row.append(`<td class="text-right">${a.signed_total || 0}</td>`);

//             companies.forEach(c => {
//                 const val = per_company[c] || 0;
//                 $row.append(`<td class="text-right">${val}</td>`);
//             });

//             $row.append(`<td class="text-right">${a.kpi_min || ''}</td>`);
//             $row.append(`<td class="text-right">${a.kpi_max || ''}</td>`);

//             this.$tbody.append($row);
//         });

//         this.$tfoot.empty();
//         if (companies.length) {
//             const $tr = $('<tr style="font-weight:bold;"></tr>');
//             $tr.append(`<td>${__('Total')}</td>`);
//             $tr.append(`<td class="text-right">${totals.signed_total || 0}</td>`);

//             companies.forEach(c => {
//                 const tv = (totals.per_company && totals.per_company[c]) || 0;
//                 $tr.append(`<td class="text-right">${tv}</td>`);
//             });

//             $tr.append('<td></td><td></td>');
//             this.$tfoot.append($tr);
//         }
//     }
// };
