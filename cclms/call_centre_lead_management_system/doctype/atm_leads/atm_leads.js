// Copyright (c) 2024, Galaxy and contributors
// For license information, please see license.txt

(() => {
    const OPENING_HOURS_PAYLOAD_FIELD = "opening_hours_payload";
    const MAP_PREFILL_FIELDS = ["opening_hours_payload", "opening_hours", "hours", "source"];

    function getRouteParams() {
        try {
            return new URLSearchParams(window.location.search || "");
        } catch (error) {
            return null;
        }
    }

    function isMapPrefillContext() {
        const routeOptions = frappe.route_options || {};
        if (routeOptions.source === "Google Maps") {
            return true;
        }
        if (MAP_PREFILL_FIELDS.some((fieldname) => routeOptions[fieldname])) {
            return true;
        }

        const params = getRouteParams();
        if (!params) {
            return false;
        }
        return MAP_PREFILL_FIELDS.some((fieldname) => params.get(fieldname));
    }

    function normalizeOpeningHoursTableValue(value) {
        if (Array.isArray(value)) {
            return value;
        }
        return [];
    }

    function sanitizeOpeningHoursField(frm) {
        if (Array.isArray(frm.doc.opening_hours)) {
            if (isMapPrefillContext() && frm.doc.hours) {
                frm.set_value("hours", "");
            }
            return;
        }

        frm.doc.opening_hours = normalizeOpeningHoursTableValue(frm.doc.opening_hours);
        if (isMapPrefillContext() && frm.doc.hours) {
            frm.doc.hours = "";
        }

        if (frm.fields_dict && frm.fields_dict.opening_hours) {
            frm.refresh_field("opening_hours");
        }
        if (frm.fields_dict && frm.fields_dict.hours) {
            frm.refresh_field("hours");
        }
    }

    function getOpeningHoursPayload() {
        const routeOptions = frappe.route_options || {};
        if (routeOptions[OPENING_HOURS_PAYLOAD_FIELD]) {
            return routeOptions[OPENING_HOURS_PAYLOAD_FIELD];
        }

        try {
            const params = new URLSearchParams(window.location.search || "");
            return params.get(OPENING_HOURS_PAYLOAD_FIELD) || "";
        } catch (error) {
            return "";
        }
    }

    function clearOpeningHoursPayload() {
        const routeOptions = frappe.route_options || {};
        delete routeOptions[OPENING_HOURS_PAYLOAD_FIELD];
        delete routeOptions.opening_hours;
        delete routeOptions.hours;
        delete routeOptions.source;

        try {
            const url = new URL(window.location.href);
            let changed = false;
            for (const fieldname of MAP_PREFILL_FIELDS) {
                if (url.searchParams.has(fieldname)) {
                    url.searchParams.delete(fieldname);
                    changed = true;
                }
            }
            if (changed) {
                window.history.replaceState({}, document.title, url.toString());
            }
        } catch (error) {
        }
    }

    function consumeOpeningHoursRoutePayload(frm) {
        sanitizeOpeningHoursField(frm);

        if (!frm.is_new()) {
            return;
        }

        const rawPayload = getOpeningHoursPayload();
        if (!rawPayload) {
            return;
        }

        let rows = rawPayload;
        if (typeof rawPayload === "string") {
            try {
                rows = JSON.parse(rawPayload);
            } catch (error) {
                console.warn("Unable to parse opening hours payload", error);
                clearOpeningHoursPayload();
                return;
            }
        }

        if (!Array.isArray(rows) || !rows.length) {
            clearOpeningHoursPayload();
            return;
        }

        frappe.model.clear_table(frm.doc, "opening_hours");
        rows.forEach((row) => {
            const child = frm.add_child("opening_hours");
            child.weekday = row.weekday || "";
            child.opening_time = row.opening_time || "";
            child.closing_time = row.closing_time || "";
        });

        if (frm.doc.hours) {
            frm.set_value("hours", "");
        }

        frm.refresh_field("opening_hours");
        clearOpeningHoursPayload();
    }

    frappe.ui.form.on("ATM Leads", {
        onload(frm) {
            sanitizeOpeningHoursField(frm);
            consumeOpeningHoursRoutePayload(frm);
        },
        refresh(frm) {
            sanitizeOpeningHoursField(frm);
            consumeOpeningHoursRoutePayload(frm);

            // ── "Duplicate for Companies" button (Sales User only, saved docs) ──
            if (!frm.is_new() && frappe.user_roles.includes("Sales User")) {
                frm.add_custom_button(__("Duplicate for Companies"), () => {
                    _dupOpenDialog(frm);
                }, __("Actions"));
            }
        },
        validate(frm) {
            sanitizeOpeningHoursField(frm);

            // "Please select company" on save — not on form init.
            if (!frm.doc.company) {
                frappe.validated = false;
                frappe.msgprint({
                    title: __("Company Not Selected"),
                    indicator: "orange",
                    message: __("Please select a company before saving this lead."),
                });
            }
        },
        before_save(frm) {
            // Skip dedup entirely for committed states — allow self-state re-save
            const COMMITTED = ["Signed", "Installed", "Converted"];
            if (COMMITTED.includes(frm.doc.workflow_state)) {
                return;
            }

            // Skip if we already ran the check this save cycle
            if (frm._dedupChecked) {
                frm._dedupChecked = false;
                return;
            }

            // Halt the default save; run async dedup check first
            frappe.validated = false;
            _runDedupCheck(frm);
        },
    });

    // =========================================================================
    // Dedup: async pre-save check + rich dialog
    // =========================================================================

    const _STATE_COLORS = {
        "Signed":           "#16a34a",
        "Installed":        "#2563eb",
        "Pending":          "#f59e0b",
        "Approved":         "#16a34a",
        "Rejected":         "#ef4444",
        "Draft":            "#6b7280",
        "Cancelled":        "#6b7280",
        "Disputed":         "#f97316",
        "Not Interested":   "#ef4444",
        "Interested":       "#10b981",
        "Call Back":        "#8b5cf6",
        "Agreement Sent":   "#0ea5e9",
        "Pending Sign":     "#f59e0b",
        "Converted":        "#2563eb",
        "Re Approval":      "#f97316",
        "Signed Rejected":  "#ef4444",
        "Hide":             "#6b7280",
        "Not Qualified":    "#ef4444",
        "Called":           "#8b5cf6",
    };

    function _stateColor(state) {
        return _STATE_COLORS[state] || "#6b7280";
    }

    function _stateBadge(state) {
        const c = _stateColor(state);
        return `<span style="background:${c};color:#fff;padding:1px 8px;border-radius:999px;
                             font-size:10px;font-weight:700;letter-spacing:.04em;white-space:nowrap">
                  ${frappe.utils.escape_html(state || "Draft")}
                </span>`;
    }

    function _runDedupCheck(frm) {
        frappe.call({
            method: "cclms.call_centre_lead_management_system.doctype.atm_leads.atm_leads.check_location_conflict",
            args: {
                full_address: frm.doc.full_address  || "",
                address:      frm.doc.address       || "",
                zip_code:     frm.doc.zip_code       || "",
                latitude:     frm.doc.latitude       || "",
                longitude:    frm.doc.longitude      || "",
                company:      frm.doc.company        || "",
                lead_name:    frm.doc.name           || "__new__",
            },
            freeze: true,
            freeze_message: __("Checking location availability…"),
            callback(r) {
                const conflict = r && r.message;
                if (!conflict || !conflict.type) {
                    frm._dedupChecked = true;
                    frm.save();
                } else {
                    _showDedupDialog(frm, conflict);
                }
            },
            error() {
                frm._dedupChecked = true;
                frm.save();
            },
        });
    }

    function _showDedupDialog(frm, conflict) {
        const stateColor = _stateColor(conflict.state);
        const leadUrl    = `/app/atm-leads/${encodeURIComponent(conflict.lead)}`;

        let title, headerColor, bodyHtml;

        if (conflict.type === "permanent") {
            title       = __("🔒 Location Permanently Locked");
            headerColor = "#ef4444";

            bodyHtml = `
<div style="font-family:var(--font-stack,inherit);line-height:1.6">
  <div style="background:linear-gradient(135deg,#fef2f2 0%,#fee2e2 100%);
              border:1px solid #fca5a5;border-radius:10px;
              padding:14px 18px;margin-bottom:18px;
              display:flex;align-items:center;gap:12px">
    <span style="font-size:28px;line-height:1">⛔</span>
    <div>
      <div style="font-weight:700;color:#b91c1c;font-size:14px">${__("Committed Deal – No New Leads Allowed")}</div>
      <div style="color:#6b7280;font-size:12px;margin-top:2px">${__("This ATM location is permanently reserved. No company can create a new lead here.")}</div>
    </div>
  </div>
  <div style="border:1px solid var(--border-color,#e5e7eb);border-radius:10px;overflow:hidden;margin-bottom:14px">
    <div style="background:var(--subtle-bg,#f9fafb);padding:10px 16px;border-bottom:1px solid var(--border-color,#e5e7eb);
                font-weight:600;font-size:12px;color:var(--text-muted,#6b7280);text-transform:uppercase;letter-spacing:.05em">
      ${__("Existing Lead")}
    </div>
    <div style="padding:14px 16px;display:grid;gap:10px">
      <div style="display:flex;align-items:center;gap:10px">
        <span style="width:80px;font-size:12px;color:var(--text-muted,#6b7280)">${__("Lead")}</span>
        <a href="${leadUrl}" target="_blank" style="font-weight:700;color:var(--primary,#2563eb);font-size:13px;text-decoration:none;border-bottom:1px dashed currentColor">
          ${frappe.utils.escape_html(conflict.lead)}
        </a>
      </div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="width:80px;font-size:12px;color:var(--text-muted,#6b7280)">${__("State")}</span>
        ${_stateBadge(conflict.state)}
      </div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="width:80px;font-size:12px;color:var(--text-muted,#6b7280)">${__("Company")}</span>
        <span style="font-size:13px;font-weight:500">${frappe.utils.escape_html(conflict.company || __("Unknown"))}</span>
      </div>
    </div>
  </div>
  <p style="color:#b91c1c;font-size:12px;margin:0;padding:0 4px">${__("Contact the lead owner to proceed with this location.")}</p>
</div>`;

        } else {
            title       = __("⏱ Location Locked – {0}-Day Window", [conflict.window]);
            headerColor = "#f59e0b";
            const elapsed  = conflict.window - conflict.remaining_days;
            const pct      = Math.min(100, Math.round((elapsed / conflict.window) * 100));
            const barColor = conflict.remaining_days <= 3 ? "#ef4444"
                           : conflict.remaining_days <= 7 ? "#f97316" : "#f59e0b";

            bodyHtml = `
<div style="font-family:var(--font-stack,inherit);line-height:1.6">
  <div style="background:linear-gradient(135deg,#fffbeb 0%,#fef3c7 100%);
              border:1px solid #fcd34d;border-radius:10px;
              padding:14px 18px;margin-bottom:18px;
              display:flex;align-items:center;gap:12px">
    <span style="font-size:28px;line-height:1">⚠️</span>
    <div>
      <div style="font-weight:700;color:#92400e;font-size:14px">${__("Your company already has an active lead at this location")}</div>
      <div style="color:#6b7280;font-size:12px;margin-top:2px">${__("Update the existing lead or wait for the lock window to expire.")}</div>
    </div>
  </div>
  <div style="border:1px solid var(--border-color,#e5e7eb);border-radius:10px;overflow:hidden;margin-bottom:14px">
    <div style="background:var(--subtle-bg,#f9fafb);padding:10px 16px;border-bottom:1px solid var(--border-color,#e5e7eb);
                font-weight:600;font-size:12px;color:var(--text-muted,#6b7280);text-transform:uppercase;letter-spacing:.05em">
      ${__("Existing Lead")}
    </div>
    <div style="padding:14px 16px;display:grid;gap:10px">
      <div style="display:flex;align-items:center;gap:10px">
        <span style="width:80px;font-size:12px;color:var(--text-muted,#6b7280)">${__("Lead")}</span>
        <a href="${leadUrl}" target="_blank" style="font-weight:700;color:var(--primary,#2563eb);font-size:13px;text-decoration:none;border-bottom:1px dashed currentColor">
          ${frappe.utils.escape_html(conflict.lead)}
        </a>
      </div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="width:80px;font-size:12px;color:var(--text-muted,#6b7280)">${__("State")}</span>
        ${_stateBadge(conflict.state)}
      </div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="width:80px;font-size:12px;color:var(--text-muted,#6b7280)">${__("Created")}</span>
        <span style="font-size:13px">${conflict.age_days} ${conflict.age_days === 1 ? __("day ago") : __("days ago")}</span>
      </div>
    </div>
  </div>
  <div style="border:1px solid ${barColor}44;border-radius:10px;overflow:hidden">
    <div style="background:${barColor}18;padding:10px 16px;border-bottom:1px solid ${barColor}44;
                display:flex;justify-content:space-between;align-items:center">
      <span style="font-weight:600;font-size:12px;color:var(--text-muted,#6b7280);text-transform:uppercase;letter-spacing:.05em">
        ${__("Lock Window Countdown")}
      </span>
      <span style="font-weight:800;font-size:16px;color:${barColor}">
        ${conflict.remaining_days} ${conflict.remaining_days === 1 ? __("day left") : __("days left")}
      </span>
    </div>
    <div style="padding:14px 16px">
      <div style="background:${barColor}22;border-radius:999px;height:12px;overflow:hidden;margin-bottom:6px">
        <div style="background:${barColor};width:${pct}%;height:100%;border-radius:999px"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted,#9ca3af)">
        <span>${__("Day 0")}</span>
        <span style="font-weight:600;color:${barColor}">${__("Day {0} of {1}", [elapsed, conflict.window])}</span>
        <span>${__("Day {0}", [conflict.window])}</span>
      </div>
    </div>
  </div>
</div>`;
        }

        const d = new frappe.ui.Dialog({
            title,
            fields: [{ fieldtype: "HTML", options: bodyHtml }],
            primary_action_label:   __("View Existing Lead"),
            secondary_action_label: __("Close"),
            primary_action() { d.hide(); frappe.set_route("Form", "ATM Leads", conflict.lead); },
            secondary_action() { d.hide(); },
        });
        d.show();
        setTimeout(() => {
            d.$wrapper.find(".modal-header").css("border-left", `4px solid ${headerColor}`);
            d.$wrapper.find(".modal-title").css("color", headerColor);
        }, 30);
    }

    // =========================================================================
    // Duplicate for Companies – dialog + execution
    // =========================================================================

    const _DUP_STATUS_CFG = {
        available: { icon: "✅", color: "#16a34a", bg: "#f0fdf4", border: "#86efac", label: "Available",    selectable: true  },
        source:    { icon: "📌", color: "#2563eb", bg: "#eff6ff", border: "#93c5fd", label: "Current Lead", selectable: false },
        locked:    { icon: "⏱",  color: "#d97706", bg: "#fffbeb", border: "#fcd34d", label: "Locked",       selectable: false },
        committed: { icon: "🔒", color: "#dc2626", bg: "#fef2f2", border: "#fca5a5", label: "Committed",    selectable: false },
    };

    function _dupOpenDialog(frm) {
        const loadD = new frappe.ui.Dialog({
            title: __("Duplicate for Companies"),
            fields: [{ fieldtype: "HTML", options:
                `<div style="text-align:center;padding:32px;color:var(--text-muted,#6b7280)">
                   <div style="font-size:28px;margin-bottom:10px">⏳</div>
                   <div>${__("Checking company availability…")}</div>
                 </div>` }],
        });
        loadD.show();

        frappe.call({
            method: "cclms.call_centre_lead_management_system.doctype.atm_leads.atm_leads.get_company_availability_for_location",
            args: {
                lead_name:      frm.doc.name          || "__new__",
                full_address:   frm.doc.full_address  || "",
                address:        frm.doc.address       || "",
                zip_code:       frm.doc.zip_code       || "",
                latitude:       frm.doc.latitude       || "",
                longitude:      frm.doc.longitude      || "",
                source_company: frm.doc.company        || "",
            },
            callback(r) {
                loadD.hide();
                const companies = (r && r.message) || [];
                if (!companies.length) { frappe.msgprint(__("No operator companies found.")); return; }
                _dupRenderDialog(frm, companies);
            },
            error() {
                loadD.hide();
                frappe.msgprint(__("Failed to load company availability. Please try again."));
            },
        });
    }

    function _dupRenderDialog(frm, companies) {
        const available  = companies.filter(c => c.status === "available");
        const locked     = companies.filter(c => c.status === "locked");
        const committed  = companies.filter(c => c.status === "committed");
        const source     = companies.filter(c => c.status === "source");
        const ordered    = [...available, ...locked, ...source, ...committed];

        function _card(co) {
            const cfg   = _DUP_STATUS_CFG[co.status] || _DUP_STATUS_CFG.available;
            const chkId = "dup_co_" + co.name.replace(/[^a-z0-9]/gi, "_");
            const dis   = cfg.selectable ? "" : "disabled";
            const op    = cfg.selectable ? "1" : "0.62";
            const cur   = cfg.selectable ? "pointer" : "default";
            let meta = "";
            if (co.status === "locked") {
                const rem = co.remaining_days || 0;
                const pct = Math.min(100, Math.round(((15 - rem) / 15) * 100));
                const bc  = rem <= 3 ? "#dc2626" : rem <= 7 ? "#f97316" : "#d97706";
                const lnk = co.lead
                    ? `<a href="/app/atm-leads/${encodeURIComponent(co.lead)}" target="_blank"
                          style="color:${cfg.color};font-weight:600">${frappe.utils.escape_html(co.lead)}</a>`
                    : "";
                meta = `<div style="margin-top:5px;font-size:11px;color:${cfg.color}">
                          ${__("Locked – {0} day(s) remaining", [rem])} ${lnk} ${_stateBadge(co.lead_state)}
                        </div>
                        <div style="background:#e5e7eb;border-radius:999px;height:5px;overflow:hidden;margin-top:5px">
                          <div style="background:${bc};width:${pct}%;height:100%;border-radius:999px"></div>
                        </div>`;
            } else if (co.status === "committed") {
                const lnk = co.lead
                    ? `<a href="/app/atm-leads/${encodeURIComponent(co.lead)}" target="_blank"
                          style="color:${cfg.color};font-weight:600">${frappe.utils.escape_html(co.lead)}</a>`
                    : "";
                meta = `<div style="margin-top:4px;font-size:11px;color:${cfg.color}">
                          ${__("Committed deal:")} ${lnk} ${_stateBadge(co.lead_state)}
                        </div>`;
            } else if (co.status === "source") {
                meta = `<div style="margin-top:3px;font-size:11px;color:${cfg.color}">${__("This lead's current company")}</div>`;
            }
            return `<label for="${chkId}"
                           style="display:flex;align-items:flex-start;gap:12px;
                                  background:${cfg.bg};border:1px solid ${cfg.border};
                                  border-radius:10px;padding:12px 14px;margin-bottom:8px;
                                  cursor:${cur};opacity:${op}">
                      <input type="checkbox" id="${chkId}"
                             data-name="${frappe.utils.escape_html(co.name)}"
                             data-op="${frappe.utils.escape_html(co.operator_name)}"
                             ${dis}
                             style="width:16px;height:16px;margin-top:3px;flex-shrink:0;cursor:${cur}">
                      <div style="flex:1;min-width:0">
                        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                          <span style="font-weight:700;font-size:13px">${cfg.icon}&nbsp;${frappe.utils.escape_html(co.operator_name)}</span>
                          <span style="background:${cfg.color}22;color:${cfg.color};
                                       padding:1px 8px;border-radius:999px;font-size:10px;font-weight:700">${_(cfg.label)}</span>
                        </div>
                        ${meta}
                      </div>
                    </label>`;
        }

        const badge = (txt, bg, color, border) =>
            `<span style="background:${bg};color:${color};border:1px solid ${border};
                          padding:4px 12px;border-radius:999px;font-size:12px;font-weight:600">${txt}</span>`;

        const summaryHtml = `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
          ${available.length  ? badge(`${available.length} ${__("Available")}`,  "#f0fdf4","#16a34a","#86efac") : ""}
          ${locked.length     ? badge(`${locked.length} ${__("Locked")}`,        "#fffbeb","#d97706","#fcd34d") : ""}
          ${committed.length  ? badge(`${committed.length} ${__("Committed")}`,  "#fef2f2","#dc2626","#fca5a5") : ""}
          ${source.length     ? badge(__("1 Current"),                           "#eff6ff","#2563eb","#93c5fd") : ""}
        </div>`;

        const listHtml = `<div style="font-family:var(--font-stack,inherit)">
          ${summaryHtml}
          <div style="position:relative;margin-bottom:12px">
            <span style="position:absolute;left:10px;top:50%;transform:translateY(-50%);color:#9ca3af">🔍</span>
            <input id="dup_search" type="text" placeholder="${__("Search companies…")}"
                   style="width:100%;box-sizing:border-box;padding:8px 10px 8px 32px;
                          border:1px solid var(--border-color,#e5e7eb);border-radius:8px;font-size:13px;outline:none">
          </div>
          <div style="display:flex;gap:10px;margin-bottom:10px;font-size:12px">
            <a id="dup_sel_all" href="#" style="color:#2563eb;text-decoration:none;font-weight:600">${__("Select All Available")}</a>
            <span style="color:#e5e7eb">|</span>
            <a id="dup_clear_all" href="#" style="color:#6b7280;text-decoration:none">${__("Clear All")}</a>
          </div>
          <div id="dup_co_list" style="max-height:340px;overflow-y:auto;padding-right:2px">
            ${ordered.map(_card).join("")}
          </div>
          <div id="dup_sel_count" style="margin-top:10px;font-size:12px;color:#6b7280;text-align:right">
            ${__("0 companies selected")}
          </div>
        </div>`;

        const d = new frappe.ui.Dialog({
            title: __("Duplicate Lead for Companies"),
            fields: [{ fieldtype: "HTML", fieldname: "html_area", options: listHtml }],
            primary_action_label:   __("Duplicate Selected"),
            secondary_action_label: __("Close"),
            primary_action() {
                const checked = [...d.$wrapper.find("#dup_co_list input[type=checkbox]:checked")];
                if (!checked.length) {
                    frappe.show_alert({ message: __("Please select at least one company."), indicator: "orange" });
                    return;
                }
                d.hide();
                _dupExecute(frm, checked.map(el => ({ name: el.dataset.name, operator_name: el.dataset.op })));
            },
            secondary_action() { d.hide(); },
        });
        d.show();

        d.$wrapper.find("#dup_search").on("input", function () {
            const q = this.value.toLowerCase();
            d.$wrapper.find("#dup_co_list label").each(function () {
                $(this).toggle(!q || $(this).text().toLowerCase().includes(q));
            });
        });
        d.$wrapper.find("#dup_sel_all").on("click", e => {
            e.preventDefault();
            d.$wrapper.find("#dup_co_list input:not([disabled])").prop("checked", true);
            _dupUpdateCount(d);
        });
        d.$wrapper.find("#dup_clear_all").on("click", e => {
            e.preventDefault();
            d.$wrapper.find("#dup_co_list input[type=checkbox]").prop("checked", false);
            _dupUpdateCount(d);
        });
        d.$wrapper.find("#dup_co_list").on("change", "input", () => _dupUpdateCount(d));
        setTimeout(() => d.$wrapper.find(".modal-header").css("border-left", "4px solid #2563eb"), 30);
    }

    function _dupUpdateCount(d) {
        const n = d.$wrapper.find("#dup_co_list input[type=checkbox]:checked").length;
        const label = n === 0 ? __("0 companies selected")
                    : n === 1 ? __("1 company selected")
                    : __("{0} companies selected", [n]);
        d.$wrapper.find("#dup_sel_count").text(label);
        d.$wrapper.find(".btn-primary").text(
            n > 0 ? __("Duplicate {0} Selected", [n]) : __("Duplicate Selected")
        );
    }

    function _dupExecute(frm, selected) {
        const results = [];
        let rem = selected.length;
        frappe.show_progress(__("Duplicating…"), 0, selected.length, __("Please wait"));

        selected.forEach(co => {
            const copy = { ...frm.doc };
            ["name", "__islocal", "__unsaved", "docstatus", "creation", "modified",
             "modified_by", "owner", "state_history", "opening_hours"].forEach(k => delete copy[k]);

            frappe.call({
                method: "frappe.client.insert",
                args: { doc: { ...copy, doctype: "ATM Leads", company: co.name, workflow_state: "Draft", status: "Draft" } },
                callback(r) {
                    if (r && r.message) results.push({ co: co.operator_name, name: r.message.name, ok: true });
                    else               results.push({ co: co.operator_name, ok: false, err: __("Unknown error") });
                },
                error(e) {
                    results.push({ co: co.operator_name, ok: false, err: (e.message || __("Failed")) });
                },
                always() {
                    rem--;
                    frappe.show_progress(__("Duplicating…"), selected.length - rem, selected.length);
                    if (rem === 0) { frappe.hide_progress(); _dupShowResults(results); }
                },
            });
        });
    }

    function _dupShowResults(results) {
        const ok = results.filter(r => r.ok), fail = results.filter(r => !r.ok);
        const banner = ok.length === results.length
            ? `<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;
                           padding:10px 14px;margin-bottom:14px;color:#16a34a;font-weight:600">
                 ✅ ${__("All {0} lead(s) duplicated successfully!", [ok.length])}
               </div>`
            : fail.length === results.length
            ? `<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;
                           padding:10px 14px;margin-bottom:14px;color:#dc2626;font-weight:600">
                 ❌ ${__("All duplications failed.")}
               </div>`
            : `<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;
                           padding:10px 14px;margin-bottom:14px;color:#d97706;font-weight:600">
                 ⚠️ ${__("{0} succeeded, {1} failed.", [ok.length, fail.length])}
               </div>`;

        const rows = results.map(r => r.ok
            ? `<div style="display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid #f3f4f6">
                 <span style="color:#16a34a">✅</span>
                 <span style="font-weight:600;min-width:130px">${frappe.utils.escape_html(r.co)}</span>
                 <a href="/app/atm-leads/${encodeURIComponent(r.name)}" target="_blank"
                    style="color:#2563eb;font-size:12px;text-decoration:none;border-bottom:1px dashed">
                   ${frappe.utils.escape_html(r.name)}
                 </a>
               </div>`
            : `<div style="display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid #f3f4f6">
                 <span style="color:#ef4444">❌</span>
                 <span style="font-weight:600;min-width:130px">${frappe.utils.escape_html(r.co)}</span>
                 <span style="color:#ef4444;font-size:12px">${frappe.utils.escape_html(r.err || "")}</span>
               </div>`
        ).join("");

        const rd = new frappe.ui.Dialog({
            title: __("Duplication Results"),
            fields: [{ fieldtype: "HTML", options:
                `<div style="font-family:var(--font-stack,inherit)">
                   ${banner}
                   <div style="max-height:300px;overflow-y:auto">${rows}</div>
                 </div>` }],
            primary_action_label: __("Close"),
            primary_action() { rd.hide(); },
        });
        rd.show();
        const c = ok.length === results.length ? "#16a34a"
                : fail.length === results.length ? "#dc2626" : "#d97706";
        setTimeout(() => rd.$wrapper.find(".modal-header").css("border-left", `4px solid ${c}`), 30);
    }
})();

// frappe.ui.form.on("ATM Leads", {
// 	refresh(frm) {

// 	},
// });
// frappe.ui.form.on('ATM Leads', {
//     onload: function (frm) {
//         loadGoogleMapsAutocomplete(frm);
//     },

//     refresh: function (frm) {
//         // Show map if lat/lng present
//         if (frm.doc.latitude && frm.doc.longitude) {
//             frm.fields_dict.map_preview.$wrapper.html(`
//                 <iframe width="100%" height="300" frameborder="0" style="border:0"
//                 src="https://maps.google.com/maps?q=${frm.doc.latitude},${frm.doc.longitude}&z=18&output=embed" allowfullscreen></iframe>
//             `);
//         } else {
//             frm.fields_dict.map_preview.$wrapper.html("<p>No map data available.</p>");
//         }
//     }
// });

// function loadGoogleMapsAutocomplete(frm) {
//     if (!window.google || !google.maps) {
//         let script = document.createElement('script');
//         script.src = "https://maps.googleapis.com/maps/api/js?key=&libraries=places";
//         script.defer = true;
//         script.async = true;
//         script.onload = function () {
//             initAutocomplete(frm);
//         };
//         document.head.appendChild(script);
//     } else {
//         initAutocomplete(frm);
//     }
// }

// function initAutocomplete(frm) {
//     let input = frm.fields_dict.address.input;
//     let autocomplete = new google.maps.places.Autocomplete(input, { types: ['geocode'] });

//     autocomplete.addListener('place_changed', function () {
//         let place = autocomplete.getPlace();

//         if (!place.address_components) {
//             frappe.msgprint(__('Invalid address. Please select from suggestions.'));
//             return;
//         }

//         let fullAddress = place.formatted_address || input.value;

//         let parsedAddress = {
//             street_number: '',
//             route: '',
//             city: '',
//             state_code: '',
//             state: '',
//             zip: '',
//             country: ''
//         };

//         place.address_components.forEach(component => {
//             const types = component.types;
//             if (types.includes("street_number")) parsedAddress.street_number = component.long_name;
//             if (types.includes("route")) parsedAddress.route = component.long_name;
//             if (types.includes("locality")) parsedAddress.city = component.long_name;
//             if (types.includes("administrative_area_level_1")) {
//                 parsedAddress.state_code = component.short_name;
//                 parsedAddress.state = component.long_name;
//             }
//             if (types.includes("postal_code")) parsedAddress.zip = component.long_name;
//             if (types.includes("country")) parsedAddress.country = component.long_name;
//         });

//         frm.set_value('full_address', fullAddress);
//         frm.set_value('address', parsedAddress.street_number + ' ' + parsedAddress.route);
//         frm.set_value('city', parsedAddress.city);
//         frm.set_value('state_code', parsedAddress.state_code);
//         frm.set_value('state', parsedAddress.state);
//         frm.set_value('zip_code', parsedAddress.zip);
//         frm.set_value('country', parsedAddress.country);

//         // Also set lat/lng if available
//         if (place.geometry && place.geometry.location) {
//             frm.set_value('latitude', place.geometry.location.lat());
//             frm.set_value('longitude', place.geometry.location.lng());
//         }
//     });
// }

// frappe.ui.form.on('ATM Leads', {
//     validate: function(frm) {
//         // Check if the company field is selected
//         if (frm.doc.company) {
//             // Fetch permitted states from the child table of the selected company
//             frappe.call({
//                 method: "frappe.client.get_list",
//                 args: {
//                     doctype: "Permitted States", // Child Doctype name
//                     filters: {
//                         'parent': frm.doc.company // Parent field linking to the selected company
//                     },
//                     fields: ['state', 'state_code'] // Fields to retrieve for validation
//                 },
//                 async: false, // Ensure call completes before continuing
//                 callback: function(r) {
//                     if (r.message && r.message.length > 0) {
//                         // List of permitted states retrieved from the operator's child table
//                         let permitted_states = r.message;

//                         // Check if lead's state or state code matches any permitted state
//                         let is_permitted = permitted_states.some(function(d) {
//                             return (d.state === frm.doc.state) ||
//                                    (d.state_code === frm.doc.state_code);
//                         });

//                         // If no match found, block the save/submit
//                         if (!is_permitted) {
//                             frappe.validated = false; // Prevent form submission
//                             frappe.msgprint({
//                                 title: __('Not Qualified'),
//                                 message: __('This lead is not qualified for the selected operator because the state or state code is not permitted.'),
//                                 indicator: 'red'
//                             });
//                         }
//                     } else {
//                         // If no permitted states are found for the company, prevent form submission
//                         frappe.validated = false;
//                         frappe.msgprint({
//                             title: __('Validation Error'),
//                             message: __(),
//                             indicator: 'red'
//                         });
//                     }
//                 }
//             });
//         } else {
//             // If company is not selected, also prevent form submission
//             frappe.validated = false;
//             frappe.msgprint({
//                 title: __('Company Not Selected'),
//                 message: __('Please select a company before saving the lead.'),
//                 indicator: 'red'
//             });
//         }
//     }
// });
// Client script to add a button and handle lead duplication
// frappe.ui.form.on('ATM Leads', {
//     refresh: function(frm) {
//         function hasRole(role) {
//             return frappe.user_roles.includes(role);
//         }

//         // Only show the buttons if the user has the "Data Executive" role
//         if (hasRole('Sales User'))
//         // Add a button to open the company selection dialog
//         frm.add_custom_button(__('Duplicate for Companies'), function() {
//             // Fetch all operator companies
//             frappe.call({
//                 method: 'frappe.client.get_list',
//                 args: {
//                     doctype: 'Operator Companies',
//                     fields: ['name', 'operator_name']
//                 },
//                 callback: function(response) {
//                     // Filter out 'Un Bank' from the company list
//                     let companies = response.message.filter(company => company.operator_name !== 'Un Bank');
//                     open_company_selection_dialog(frm, companies);
//                 }
//             });
//         });
//     }
// });

// // Function to open the dialog box with company checkboxes
// function open_company_selection_dialog(frm, companies) {
//     let fields = companies.map(company => {
//         return {
//             fieldtype: 'Check',
//             label: company.operator_name,
//             fieldname: company.name
//         };
//     });

//     let dialog = new frappe.ui.Dialog({
//         title: __('Select Companies to Duplicate Lead'),
//         fields: fields,
//         primary_action_label: __('Duplicate'),
//         primary_action(values) {
//             // Filter selected companies
//             let selected_companies = companies.filter(company => values[company.name]);

//             // Duplicate lead for each selected company
//             duplicate_lead_for_selected_companies(frm, selected_companies);
//             dialog.hide();
//         }
//     });

//     dialog.show();
// }

// // Function to duplicate the lead for the selected companies
// function duplicate_lead_for_selected_companies(frm, selected_companies) {
//     selected_companies.forEach(company => {
//         // Duplicate the lead record for each selected company
//         frappe.call({
//             method: 'frappe.client.insert',
//             args: {
//                 doc: {
//                     doctype: 'ATM Leads',
//                     // Copy all fields from the current lead
//                     ...frm.doc,
//                     name: null, // Clear the name field to create a new record
//                     company: company.name, // Set the selected company
//                     status: 'Draft' // Set the status to Draft for the new record
//                 }
//             },
//             callback: function(response) {
//                 if (response && response.message) {
//                     frappe.show_alert({
//                         message: __('Lead duplicated for {0}', [company.operator_name]),
//                         indicator: 'green'
//                     });
//                 }
//             }
//         });
//     });
// }

// frappe.ui.form.on('ATM Leads', {
//     refresh: function(frm) {
//         // Add a button to open the company selection dialog
//         frm.add_custom_button(__('Duplicate for Companies'), function() {
//             // Fetch all operator companies
//             frappe.call({
//                 method: 'frappe.client.get_list',
//                 args: {
//                     doctype: 'Operator Companies',
//                     fields: ['name', 'operator_name']
//                 },
//                 callback: function(response) {
//                     // Open the dialog with checkboxes for each company
//                     let companies = response.message;
//                     open_company_selection_dialog(frm, companies);
//                 }
//             });
//         });
//     }
// });

// // Function to open the dialog box with company checkboxes
// function open_company_selection_dialog(frm, companies) {
//     let fields = companies.map(company => {
//         return {
//             fieldtype: 'Check',
//             label: company.operator_name,
//             fieldname: company.name
//         };
//     });

//     let dialog = new frappe.ui.Dialog({
//         title: __('Select Companies to Duplicate Lead'),
//         fields: fields,
//         primary_action_label: __('Duplicate'),
//         primary_action(values) {
//             // Filter selected companies
//             let selected_companies = companies.filter(company => values[company.name]);

//             // Duplicate lead for each selected company
//             duplicate_lead_for_selected_companies(frm, selected_companies);
//             dialog.hide();
//         }
//     });

//     dialog.show();
// }

// // Function to duplicate the lead for the selected companies
// function duplicate_lead_for_selected_companies(frm, selected_companies) {
//     selected_companies.forEach(company => {
//         // Duplicate the lead record for each selected company
//         frappe.call({
//             method: 'frappe.client.insert',
//             args: {
//                 doc: {
//                     doctype: 'ATM Leads',
//                     // Copy all fields from the current lead
//                     ...frm.doc,
//                     name: null, // Clear the name field to create a new record
//                     company: company.name, // Set the selected company
//                     status: 'Draft' // Set the status to Draft for the new record
//                 }
//             },
//             callback: function(response) {
//                 if (response && response.message) {
//                     frappe.show_alert({
//                         message: __('Lead duplicated for {0}', [company.operator_name]),
//                         indicator: 'green'
//                     });
//                 }
//             }
//         });
//     });
// }


// frappe.ui.form.on('ATM Leads', {
//     address: function(frm) {
//         // Mapping of state codes to state names
//         const stateMap = {
//             'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
//             'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
//             'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
//             'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
//             'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
//             'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
//             'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
//             'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
//             'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
//             'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
//             'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
//             'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
//             'WI': 'Wisconsin', 'WY': 'Wyoming'
//         };

//         // Function to parse address into components
//         function parseAddress(address) {
//             // Example input: "27252 Katy Fwy #700, Katy, TX 77494"
//             let addressPattern = /(.+),\s*([^,]+),\s*([A-Z]{2})\s*(\d{5})/;
//             let match = address.match(addressPattern);

//             if (match) {
//                 let streetAddress = match[1]; // Street Address
//                 let city = match[2];          // City
//                 let stateCode = match[3];     // State Code
//                 let zip = match[4];           // Zip Code
//                 let country = "United States"; // Default to US

//                 // Set parsed values to the form fields
//                 frm.set_value('address', streetAddress);
//                 frm.set_value('city', city);
//                 frm.set_value('state_code', stateCode); // State Code
//                 frm.set_value('zip_code', zip);
//                 frm.set_value('country', country);

//                 // Set the state name based on state code if state name is not available
//                 let stateName = frm.doc.state || stateMap[stateCode] || "";
//                 frm.set_value('state', stateName);
//             } else {
//                 frappe.msgprint(__('Address format is not recognized. Please ensure the format is "Street, City, State Zip".'));
//             }
//         }

//         // Get the address value and parse it
//         let address = frm.doc.address;
//         if (address) {
//             parseAddress(address);
//         }
//     }
// });
// frappe.ui.form.on('ATM Leads', {
//     refresh: function(frm) {
//         // Add button to copy data for Excel
//         frm.add_custom_button(__('Copy For Excel'), function() {
//             // Prepare the data in a tab-separated format for Excel columns
//             let excelData = [
//                 frm.doc.company || '',
//                 frm.doc.post_date || '',                  // Date (Post Date)
//                 frm.doc.executive_name || '',             // Executive Name
//                 frm.doc.workflow_status || 'In Review',            // Lead Status
//                 frm.doc.contract_length || 'TBD',         // Contract Length
//                 frm.doc.fixed || 'TBD',                   // Fixed (Base Rent)
//                 frm.doc.per_transaction || 'TBD',         // Per Transaction
//                 frm.doc.owner_name || '',                 // Owner Name
//                 frm.doc.business_type || 'N/A',           // Business Type
//                 frm.doc.business_name || 'N/A',           // Business Name
//                 frm.doc.address || 'N/A',                 // Business Street Address
//                 frm.doc.city || 'N/A',                    // City
//                 frm.doc.state_code || 'N/A',              // State/Province
//                 frm.doc.zip_code || 'N/A',          // ZIP/Postal Code
//                 frm.doc.business_phone_number || 'N/A',   // Business Phone
//                 frm.doc.personal_cell_phone || '',        // Personal Phone
//                 frm.doc.email || '',                      // Email Address
//                 frm.doc.sign_date || '',
//                 frm.doc.agreement_sent_date || '',// Signed Date
//                 frm.doc.approve_date || ''              // Installed Date
//             ];

//             // Join the array with tab characters to separate into columns
//             let tabSeparatedData = excelData.join('\t');

//             // Create a temporary textarea element to hold the tab-separated text
//             let tempTextArea = document.createElement('textarea');
//             tempTextArea.value = tabSeparatedData;
//             document.body.appendChild(tempTextArea);

//             // Select the text inside the textarea and copy it
//             tempTextArea.select();
//             tempTextArea.setSelectionRange(0, 99999); // For mobile devices

//             try {
//                 // Execute the copy command
//                 document.execCommand('copy');
//                 frappe.msgprint(__('Copied to clipboard!'));
//             } catch (err) {
//                 frappe.msgprint(__('Failed to copy: ' + err));
//             }

//             // Remove the temporary textarea
//             document.body.removeChild(tempTextArea);
//         });
//     }
// });
// frappe.ui.form.on('ATM Leads', {
//     refresh: function(frm) {
//         function hasRole(role) {
//             return frappe.user_roles.includes(role);
//         }

//         // Only show the buttons if the user has the "Data Executive" role
//         if (hasRole('Sales User'))
//         // Add button to copy data for Skype
//         frm.add_custom_button(__('Skype Approval'), function() {
//             // Define the formatted text for Skype
//             let skypeText = `
// Approval Send Request:

// Owner Name: ${frm.doc.owner_name || 'N/A'}

// Owner Mail: mailto:${frm.doc.email || 'N/A'}

// Personal Phone: ${frm.doc.personal_cell_phone || 'N/A'}

// Business Name: ${frm.doc.business_name || 'N/A'}

// Business Address: ${frm.doc.address || 'N/A'}, ${frm.doc.city || 'N/A'}, ${frm.doc.state_code || 'N/A'}, ${frm.doc.zip_code || 'N/A'}

// Business Phone: ${frm.doc.business_phone_number || 'N/A'}

// Operations Hours: ${frm.doc.hours || 'N/A'}

// Location Type: ${frm.doc.business_type || 'N/A'}

// Offer Details:

// Fixed: ${frm.doc.fixed || 'TBD'}

// Per Trans: ${frm.doc.per_transaction || 'TBD'}

// Term: ${frm.doc.contract_length || 'TBD'}

// Additional Notes: Please Send This Location For Approval. Thanks
// `;

//             // Create a temporary textarea element to hold the text
//             let tempTextArea = document.createElement('textarea');
//             tempTextArea.value = skypeText;
//             document.body.appendChild(tempTextArea);

//             // Select the text inside the textarea and copy it
//             tempTextArea.select();
//             tempTextArea.setSelectionRange(0, 99999); // For mobile devices

//             try {
//                 // Execute the copy command
//                 document.execCommand('copy');
//                 frappe.msgprint(__('Copied to clipboard!'));
//             } catch (err) {
//                 frappe.msgprint(__('Failed to copy: ' + err));
//             }

//             // Remove the temporary textarea
//             document.body.removeChild(tempTextArea);
//         });
//     }
// });

// frappe.ui.form.on('ATM Leads', {
//     onload: function(frm) {
//         // Check if the child table is empty, then fill with default values
//         if (!frm.doc.opening_hours || frm.doc.opening_hours.length === 0) {
//             const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
//             weekdays.forEach(weekday => {
//                 frm.add_child('opening_hours', {
//                     'weekday': weekday,
//                     'opening_time': '7:00 AM',
//                     'closing_time': '8:00 PM'
//                 });
//             });
//             frm.refresh_field('opening_hours');
//         }
//     }
// });
// frappe.ui.form.on('ATM Leads', {
//     refresh: function(frm) {
//         calculate_all_rows(frm); // Calculate total hours for all rows on load
//         update_average_hours(frm); // Update average hours on load
//     },
//     onload: function(frm) {
//         calculate_all_rows(frm); // Calculate total hours for all rows on load
//         update_average_hours(frm); // Update average hours on load
//     }
// });

// frappe.ui.form.on('Opening Hours', {
//     opening_time: function(frm, cdt, cdn) {
//         sync_times_if_first_row(frm, cdt, cdn);
//         update_average_hours(frm); // Update average hours when times change
//     },
//     closing_time: function(frm, cdt, cdn) {
//         sync_times_if_first_row(frm, cdt, cdn);
//         update_average_hours(frm); // Update average hours when times change
//     }
// });

// function calculate_all_rows(frm) {
//     frm.doc.opening_hours.forEach(row => {
//         calculate_total_hours(frm, row.doctype, row.name);
//     });
// }

// function calculate_total_hours(frm, cdt, cdn) {
//     var row = frappe.get_doc(cdt, cdn);

//     let opening = parseTime(row.opening_time);
//     let closing = parseTime(row.closing_time);

//     let duration = (closing - opening) / (1000 * 60 * 60); // Convert milliseconds to hours

//     if (duration < 0) {
//         duration += 24; // Adjust for overnight (e.g., 7:00 PM to 7:00 AM)
//     }

//     frappe.model.set_value(cdt, cdn, 'total_hours', duration.toFixed(2));
// }

// function sync_times_if_first_row(frm, cdt, cdn) {
//     var row = frappe.get_doc(cdt, cdn);

//     if (row.idx === 1) {
//         calculate_total_hours(frm, cdt, cdn);

//         frm.doc.opening_hours.forEach(other_row => {
//             if (other_row.name !== row.name) {
//                 frappe.model.set_value(other_row.doctype, other_row.name, 'opening_time', row.opening_time);
//                 frappe.model.set_value(other_row.doctype, other_row.name, 'closing_time', row.closing_time);
//                 calculate_total_hours(frm, other_row.doctype, other_row.name);
//             }
//         });
//     } else {
//         calculate_total_hours(frm, cdt, cdn);
//     }
// }

// function parseTime(timeStr) {
//     let [time, period] = timeStr.split(' ');
//     let [hours, minutes] = time.split(':').map(Number);

//     if (period === 'PM' && hours !== 12) hours += 12;
//     if (period === 'AM' && hours === 12) hours = 0;

//     let date = new Date();
//     date.setHours(hours, minutes, 0, 0);
//     return date;
// }

// // Function to calculate and update average hours
// function update_average_hours(frm) {
//     let totalHours = 0;
//     let rowCount = frm.doc.opening_hours.length;

//     // Sum all total hours from the child table
//     frm.doc.opening_hours.forEach(row => {
//         totalHours += parseFloat(row.total_hours || 0);
//     });

//     // Calculate average hours
//     let averageHours = rowCount ? totalHours / rowCount : 0;

//     // Round to the nearest whole number
//     let roundedAverage = Math.round(averageHours);

//     // Update the 'hours' field in the ATM Leads Doctype
//     frm.set_value('hours', `${roundedAverage} Hours`);
// }

// frappe.ui.form.on('ATM Leads', {
//     refresh: function(frm) {
//         // Function to check if the user has the "Data Executive" role
//         function hasRole(role) {
//             return frappe.user_roles.includes(role);
//         }

//         // Only show the buttons if the user has the "Data Executive" role
//         if (hasRole('Sales User')) {
//             // Create a wrapper for grouped buttons
//             frm.add_custom_button(__('Call Back'), function() {
//                 copyToClipboard([
//                     frm.doc.field ||'',
//                     frm.doc.business_name || '',
//                     frm.doc.field ||'',
//                     frm.doc.business_type || '',
//                     frm.doc.owner_name || '',
//                     frm.doc.address || 'N/A',
//                     frm.doc.business_phone_number || 'N/A',
//                     frm.doc.personal_cell_phone || 'N/A',
//                     frm.doc.email || 'N/A'
//                 ]);
//             }, __('Personal')); // Add to a group labeled "Data for Excel"
            
//             frm.add_custom_button(__('Approval Sent'), function() {
//                 copyToClipboard([
//                     frm.doc.field ||'',
//                     frm.doc.field ||'',
//                     frm.doc.business_name || '',
//                     frm.doc.business_type || '',
//                     frm.doc.owner_name || '',
//                     frm.doc.company ||'',
//                     frm.doc.field ||'',
//                     frm.doc.address || 'N/A',
//                     frm.doc.business_phone_number || 'N/A',
//                     frm.doc.personal_cell_phone || 'N/A',
//                     frm.doc.email || 'N/A'
//                 ]);
//             }, __('Personal')); // Add to the same group

//             frm.add_custom_button(__('Approved'), function() {
//                 copyToClipboard([
//                     frm.doc.field ||'',
//                     frm.doc.field ||'',
//                     frm.doc.field ||'',
//                     frm.doc.business_name || '',
//                     frm.doc.business_type || '',
//                     frm.doc.owner_name || '',
//                     frm.doc.company ||'',
//                     frm.doc.field ||'',
//                     frm.doc.address || 'N/A',
//                     frm.doc.business_phone_number || 'N/A',
//                     frm.doc.personal_cell_phone || 'N/A',
//                     frm.doc.email || 'N/A'
//                 ]);
//             }, __('Personal')); // Add to the same group


//             frm.add_custom_button(__('Agreement Sent'), function() {
//                 copyToClipboard([
//                     frm.doc.field ||'',
//                     frm.doc.business_name || '',
//                     frm.doc.business_type || '',
//                     frm.doc.field ||'',
//                     frm.doc.owner_name || '',
//                     frm.doc.company ||'',
//                     frm.doc.base_rent ||'',
//                     frm.doc.address || 'N/A',
//                     frm.doc.business_phone_number || 'N/A',
//                     frm.doc.personal_cell_phone || 'N/A',
//                     frm.doc.email || 'N/A'
//                 ]);
//             }, __('Personal')); // Add to the same group

//             frm.add_custom_button(__('Signed'), function() {
//                 copyToClipboard([
//                     frm.doc.field ||'',
//                     frm.doc.workflow_status || '',
//                     frm.doc.business_name || '',
//                     frm.doc.business_type || '',
//                     frm.doc.field ||'',
//                     frm.doc.owner_name || '',
//                     frm.doc.company ||'',
//                     frm.doc.base_rent ||'',
//                     frm.doc.address || 'N/A',
//                     frm.doc.business_phone_number || 'N/A',
//                     frm.doc.personal_cell_phone || 'N/A',
//                     frm.doc.email || 'N/A'
//                 ]);
//             }, __('Personal')); // Add to the same group

frappe.ui.form.on("ATM Leads", {
    onload(frm) {
        apply_map_prefill(frm);
    },

    refresh(frm) {
        if (frm.is_new()) {
            apply_map_prefill(frm);
        }
    },

    address(frm) {
        if (frm.is_new()) {
            lookup_duplicate_lead(frm);
        }
    },

    full_address(frm) {
        if (frm.is_new()) {
            lookup_duplicate_lead(frm);
        }
    },

    zip_code(frm) {
        if (frm.is_new()) {
            lookup_duplicate_lead(frm);
        }
    },

    business_name(frm) {
        if (frm.is_new()) {
            lookup_duplicate_lead(frm);
        }
    },

    latitude(frm) {
        if (frm.is_new()) {
            lookup_duplicate_lead(frm);
        }
    },

    longitude(frm) {
        if (frm.is_new()) {
            lookup_duplicate_lead(frm);
        }
    },
});

let duplicate_lookup_in_flight = false;

function apply_map_prefill(frm) {
    if (!frm.is_new()) {
        return;
    }

    const options = frappe.route_options || {};
    const allowedFields = [
        "business_name",
        "address",
        "full_address",
        "city",
        "state",
        "state_code",
        "zip_code",
        "country",
        "latitude",
        "longitude",
    ];

    let applied = false;
    allowedFields.forEach((fieldname) => {
        const value = options[fieldname];
        if (value === undefined || value === null || value === "") {
            return;
        }
        if (frm.doc[fieldname]) {
            return;
        }
        frm.set_value(fieldname, value);
        applied = true;
    });

    if (!applied && !frm.doc.address && !frm.doc.zip_code) {
        return;
    }

    // Run once on form open so a map-selected location immediately shows duplicate state.
    if (!frm.__map_prefill_checked) {
        frm.__map_prefill_checked = true;
        lookup_duplicate_lead(frm);
    }
}

function lookup_duplicate_lead(frm) {
    if (duplicate_lookup_in_flight) {
        return;
    }

    if (!frm.doc.address && !frm.doc.full_address && !frm.doc.zip_code) {
        return;
    }

    duplicate_lookup_in_flight = true;
    frappe.call({
        method: "cclms.api.atm_lead_helper.lookup_existing_lead",
        args: {
            address: frm.doc.address || frm.doc.full_address || "",
            zip_code: frm.doc.zip_code || "",
            business_name: frm.doc.business_name || "",
            latitude: frm.doc.latitude || "",
            longitude: frm.doc.longitude || "",
        },
        callback: function(r) {
            const result = r.message || {};
            const best = result.best_match || null;

            if (best && best.name !== frm.doc.name) {
                const distanceText = best.distance_miles !== undefined ? ` Distance: ${best.distance_miles} mi.` : "";
                frappe.show_alert({
                    message: __("Possible duplicate: {0} is already in stage {1}.{2}", [
                        best.business_name || best.name,
                        best.workflow_state || "Draft",
                        distanceText,
                    ]),
                    indicator: "orange",
                }, 10);

                if (frm.dashboard.clear_headline) {
                    frm.dashboard.clear_headline();
                }
                frm.dashboard.set_headline_alert(
                    __(
                        'Existing ATM Lead found: <a href="/app/atm-leads/{0}" target="_blank">{1}</a> is currently in <b>{2}</b>.',
                        [
                            encodeURIComponent(best.name),
                            frappe.utils.escape_html(best.business_name || best.name),
                            frappe.utils.escape_html(best.workflow_state || "Draft"),
                        ]
                    ),
                    "orange"
                );
            }
        },
        error: function() {
            duplicate_lookup_in_flight = false;
        },
        always: function() {
            duplicate_lookup_in_flight = false;
        }
    });
}

//             frm.add_custom_button(__('Not Intrested'), function() {
//                 copyToClipboard([
//                     frm.doc.field ||'',
//                     frm.doc.field ||'',
//                     frm.doc.business_name || '',
//                     frm.doc.business_type || '',
//                     frm.doc.owner_name || '',
//                     frm.doc.company ||'',
//                     frm.doc.base_rent ||'',
//                     frm.doc.address || 'N/A',
//                     frm.doc.business_phone_number || 'N/A',
//                     frm.doc.personal_cell_phone || 'N/A',
//                     frm.doc.email || 'N/A'
//                 ]);
//             }, __('Personal')); // Add to the same group

//             frm.add_custom_button(__('Denied'), function() {
//                 copyToClipboard([
//                     frm.doc.field ||'',
//                     frm.doc.field ||'',
//                     frm.doc.business_name || '',
//                     frm.doc.business_type || '',
//                     frm.doc.owner_name || '',
//                     frm.doc.company ||'',
//                     frm.doc.base_rent ||'',
//                     frm.doc.address || 'N/A',
//                     frm.doc.business_phone_number || 'N/A',
//                     frm.doc.personal_cell_phone || 'N/A',
//                     frm.doc.email || 'N/A'
//                 ]);
//             }, __('Personal')); // Add to the same group

//         }
//     }
// });

// // Function to copy data to clipboard
// function copyToClipboard(dataArray) {
//     // Join the array with tab characters to separate into columns
//     let tabSeparatedData = dataArray.join('\t');

//     // Create a temporary textarea element to hold the tab-separated text
//     let tempTextArea = document.createElement('textarea');
//     tempTextArea.value = tabSeparatedData;
//     document.body.appendChild(tempTextArea);

//     // Select the text inside the textarea and copy it
//     tempTextArea.select();
//     tempTextArea.setSelectionRange(0, 99999); // For mobile devices

//     try {
//         // Execute the copy command
//         document.execCommand('copy');
//         frappe.msgprint(__('Copied to clipboard!'));
//     } catch (err) {
//         frappe.msgprint(__('Failed to copy: ' + err));
//     }

//     // Remove the temporary textarea
//     document.body.removeChild(tempTextArea);
// }
