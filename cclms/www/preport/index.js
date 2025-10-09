/* eslint-env browser */
/* globals frappe, Highcharts */
(function () {
  "use strict";

  const REQUIRE_LOGIN = false;

  const $ = (id) => document.getElementById(id);
  const setText = (id, val) => { const el = $(id); if (el) el.textContent = val ?? "—"; };

  const todayISO = () => new Date().toISOString().slice(0, 10);
  const monthStartISO = () => { const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10); };

  async function call(method, args = {}) {
    try {
      const r = await frappe.call({ method, args });
      return r && r.message;
    } catch (e) {
      const j = (e && e.xhr && e.xhr.responseJSON) || {};
      const msg = j.exception || j.message || "Server error";
      frappe.msgprint({ title: "API Error", message: `<b>${frappe.utils.escape_html(method)}</b><br>${msg}`, indicator: "red" });
      throw e;
    }
  }

  function getFilters() {
    return {
      start_date: $("sdate").value || null,
      end_date: $("edate").value || null,
      company: ($("company").value || "").trim() || null,
      executive_name: ($("executive").value || "").trim() || null,
    };
  }

  function setDefaults() {
    if (!$("sdate").value) $("sdate").value = monthStartISO();
    if (!$("edate").value) $("edate").value = todayISO();
    if (!$("mp_month").value) $("mp_month").value = ($("edate").value || todayISO()).slice(0, 7);
  }

  // --- Conversions (Tailwind cards) ---
  async function renderConversions() {
    const f = getFilters();
    const c = await call("cclms.api.reports.conversions_summary.get_conversions_summary", f);
    const host = $("conv_kpis");
    if (!c || !host) return;

    const card = (label, value, sub = "") => `
      <div class="bg-white ring-1 ring-slate-200 rounded-2xl shadow-sm p-4">
        <div class="text-sm text-slate-500">${label}</div>
        <div class="mt-1 text-2xl font-semibold">${value}${sub ? ` <span class="ml-1 text-sm font-medium text-slate-500">${sub}</span>` : ""}</div>
      </div>`;

    host.innerHTML = `
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        ${card("Total Leads", c.cohort_total)}
        ${card("Rejected / Total", c.rejected, `${c.ratios.rejected_vs_total_pct}%`)}
        ${card("Approved / Total", c.approved, `${c.ratios.approved_vs_total_pct}%`)}
        ${card("Agreement Sent / Approved", c.agreement_sent, `${c.ratios.agrsent_vs_approved_pct}%`)}
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
        ${card("Signed+Converted / Total", c.signed_plus_converted, `${c.ratios.signedplus_vs_total_pct}%`)}
        ${card("Signed+Converted / Approved", c.signed_plus_converted, `${c.ratios.signedplus_vs_approved_pct}%`)}
        ${card("Signed+Converted / Agreement Sent", c.signed_plus_converted, `${c.ratios.signedplus_vs_agrsent_pct}%`)}
        ${card("Converted (count)", c.converted)}
      </div>
    `;
  }

  // --- Executives table ---
  async function renderExecutives() {
    const f = getFilters();
    const data = await call("cclms.api.reports.executive_overview.get_executive_overview", {
      start_date: f.start_date, end_date: f.end_date, company: f.company,
    });
    const table = $("exec_table");
    if (!table) return;

    const rows = (data && data.rows) || [];
    const tbody = table.querySelector("tbody");
    const tfoot = table.querySelector("tfoot");

    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="px-3 py-3 text-slate-500">No executives with leads in this window.</td></tr>`;
      if (tfoot) tfoot.innerHTML = "";
      return;
    }

    let total_post = 0, approved = 0, sent = 0, signed = 0, converted = 0, sc = 0;

    tbody.innerHTML = rows.map((r) => {
      total_post += Number(r.total_post || 0);
      approved += Number(r.approved || 0);
      sent += Number(r.agreement_sent || 0);
      signed += Number(r.signed || 0);
      converted += Number(r.converted || 0);
      sc += Number(r.signed_plus_converted || 0);
      const name = frappe.utils.escape_html(r.executive_name || "-");
      return `
        <tr class="odd:bg-white even:bg-slate-50">
          <td class="px-3 py-2">${name}</td>
          <td class="px-3 py-2 text-right">${r.total_post}</td>
          <td class="px-3 py-2 text-right">${r.approved}</td>
          <td class="px-3 py-2 text-right">${r.agreement_sent}</td>
          <td class="px-3 py-2 text-right">${r.signed}</td>
          <td class="px-3 py-2 text-right">${r.converted}</td>
          <td class="px-3 py-2 text-right">${r.signed_plus_converted}</td>
        </tr>`;
    }).join("");

    if (tfoot) {
      const agents = rows.length;
      const sign_vs_total_pct = total_post > 0 ? Math.round((sc / total_post) * 100) : 0;
      const rej_vs_total_pct = total_post > 0 ? Math.round(((total_post - approved) / total_post) * 100) : 0;

      tfoot.innerHTML = `
        <tr class="border-t border-slate-200 bg-slate-100">
          <th class="px-3 py-2 text-left">Total (${agents} Execs)</th>
          <th class="px-3 py-2 text-right">${total_post}</th>
          <th class="px-3 py-2 text-right">${approved}</th>
          <th class="px-3 py-2 text-right">${sent}</th>
          <th class="px-3 py-2 text-right">${signed}</th>
          <th class="px-3 py-2 text-right">${converted}</th>
          <th class="px-3 py-2 text-right">${sc} (${sign_vs_total_pct}%)</th>
        </tr>
        <tr>
          <td colspan="7" class="px-3 py-2 text-center text-slate-500">
            <span class="mr-4"><strong>Rejected vs Total:</strong> ${rej_vs_total_pct}%</span>
            <span><strong>Signed+Converted vs Total:</strong> ${sign_vs_total_pct}%</span>
          </td>
        </tr>`;
    }
  }

  // --- Charts ---
  async function renderStateByExecutive() {
    const f = getFilters();
    const data = await call("cclms.api.reports.state_by_executive.get_state_counts_by_executive", f);
    const targetId = "state_exec_chart";
    const el = $(targetId);

    if (!el) return;
    if (!data || !data.categories || !data.categories.length) {
      el.innerHTML = '<div class="text-slate-500">No data for current filters.</div>';
      return;
    }

    Highcharts.chart(targetId, {
      chart: { type: "column", scrollablePlotArea: { minWidth: Math.max(900, data.categories.length * 90), scrollPositionX: 0 } },
      title: { text: "States by Executive (Snapshot, Draft excluded)" },
      xAxis: { categories: data.categories, crosshair: true },
      yAxis: { min: 0, title: { text: "Leads" } },
      legend: { enabled: true },
      tooltip: { shared: true },
      plotOptions: { column: { stacking: "normal" } },
      series: data.series,
      credits: { enabled: false },
    });
  }

  async function renderTrend() {
    const f = getFilters();
    const data = await call("cclms.api.reports.timeline_trends.get_multi_trends", {
      start_date: f.start_date, end_date: f.end_date, company: f.company, executive_name: f.executive_name,
    });
    const targetId = "trend_chart";
    const el = $(targetId);

    if (!el) return;
    if (!data || !data.categories || !data.categories.length) {
      el.innerHTML = '<div class="text-slate-500">No trend data for current filters.</div>';
      return;
    }

    Highcharts.chart(targetId, {
      title: { text: "Monthly Events" },
      xAxis: { categories: data.categories },
      yAxis: { title: { text: "Count" } },
      legend: { enabled: true },
      series: data.series,
      credits: { enabled: false },
    });
  }

  async function renderMonthlyPerformance() {
    const f = getFilters();
    const month = ($("mp_month").value || "").trim() || ($("edate").value || todayISO()).slice(0, 7);

    const mp = await call("cclms.api.reports.monthly_performance.get_monthly_performance", {
      month, company: f.company, executive_name: f.executive_name,
    });

    const c = mp.counts, r = mp.ratios, L = mp.lag_buckets || {};
    setText("mp_signed", c.signed_in_month);
    setText("mp_converted", c.converted_in_month);
    setText("mp_signed_plus", c.signed_plus_converted_in_month);
    setText("mp_same", c.signed_same_month);
    setText("mp_carry", c.signed_carry_in);
    setText("mp_conv_same", c.converted_same_month);
    setText("mp_conv_carry", c.converted_carry_in);
    setText("mp_total", c.total_created);
    setText("mp_appr", c.approved_in_month);
    setText("mp_sent", c.agreement_sent_in_month);
    setText("mp_s_t", r.sign_vs_total_pct != null ? `${r.sign_vs_total_pct}%` : "—");
    setText("mp_c_t", r.converted_vs_total_pct != null ? `${r.converted_vs_total_pct}%` : "—");
    setText("mp_sc_t", r.signed_plus_converted_vs_total_pct != null ? `${r.signed_plus_converted_vs_total_pct}%` : "—");

    $("mp_lag").innerHTML =
      `0–7: <b>${L.d0_7 || 0}</b> &nbsp;|&nbsp; 8–30: <b>${L.d8_30 || 0}</b> &nbsp;|&nbsp; 31–60: <b>${L.d31_60 || 0}</b> &nbsp;|&nbsp; 61–90: <b>${L.d61_90 || 0}</b> &nbsp;|&nbsp; 90+: <b>${L.d90p || 0}</b>`;
  }

  async function runAll() {
    await renderConversions();
    await renderExecutives();
    await renderStateByExecutive();
    await renderTrend();
    await renderMonthlyPerformance();
  }

  frappe.ready(function () {
    if (REQUIRE_LOGIN && frappe.session.user === "Guest") {
      frappe.msgprint("Please login to view this report");
      return;
    }

    setDefaults();

    $("apply").addEventListener("click", () => { runAll().catch((e) => console.error(e)); });
    $("reset").addEventListener("click", () => {
      $("company").value = "";
      $("executive").value = "";
      setDefaults();
      runAll().catch((e) => console.error(e));
    });
    $("run_mp").addEventListener("click", () => { renderMonthlyPerformance().catch((e) => console.error(e)); });

    runAll().catch((e) => console.error(e));
  });
})();
// ######################################################
// /* cclms/www/preport/index.js */
// /* eslint-env browser */
// /* globals frappe, Highcharts */

// // frappe.ready(function() {
// //     if (frappe.session.user === "Guest") {
// //         frappe.msgprint("Please login to view this report");
// //         return;
// //     }
// //     frappe.call({
// //         method: "cclms.api.bitcoin_depot_report.get_bitcoin_depot_report",
// //         callback: function(response) {
// //             const data = response.message;
// //             const table = document.getElementById("bitcoinDepotTable");
            
// //             // Build header with double rows
// //             const header = `
// //                 <tr>
// //                     <th rowspan="2" style="min-width: 150px">Executive</th>
// //                     <th rowspan="2" style="min-width: 150px">Pseudo Name</th>
// //                     <th rowspan="2" style="min-width: 100px">Leads<br>Generated</th>
// //                     <th colspan="2" class="text-center">Pending Approval</th>
// //                     <th colspan="2" class="text-center">Approved</th>
// //                     <th colspan="2" class="text-center">Rejected</th>
// //                     <th colspan="2" class="text-center">Agreement Sent</th>
// //                     <th colspan="2" class="text-center">Signed</th>
// //                 </tr>
// //                 <tr>
// //                     <!-- Pending Approval Sub-headers -->
// //                     <th style="min-width: 80px">Count</th>
// //                     <th style="min-width: 80px">Ratio</th>

// //                     <!-- Approved Sub-headers -->
// //                     <th style="min-width: 80px">Count</th>
// //                     <th style="min-width: 80px">Ratio</th>
                    
// //                     <!-- Rejected Sub-headers -->
// //                     <th style="min-width: 80px">Count</th>
// //                     <th style="min-width: 80px">Ratio</th>
                    
// //                     <!-- Agreement Sent Sub-headers -->
// //                     <th style="min-width: 80px">Count</th>
// //                     <th style="min-width: 80px">Ratio</th>
                    
// //                     <!-- Signed Sub-headers -->
// //                     <th style="min-width: 80px">Count</th>
// //                     <th style="min-width: 80px">Ratio</th>
// //                 </tr>`;
            
// //             table.querySelector('thead').innerHTML = header;
            
// //             // Build body
// //             let body = '';
// //             data.report_data.forEach(agent => {
// //                 const approvalRatio = agent.lead_generated > 0 
// //                     ? Math.round((agent.approved / agent.lead_generated) * 100) 
// //                     : 0;
                
// //                 const pendingRatio = agent.lead_generated > 0 
// //                     ? Math.round((agent.pending_approved / agent.lead_generated) * 100) 
// //                     : 0;
                
// //                 const agreementRatio = agent.lead_generated > 0 
// //                     ? Math.round((agent.agreement_sent / agent.lead_generated) * 100) 
// //                     : 0;
                
// //                 const signedRatio = agent.lead_generated > 0 
// //                     ? Math.round((agent.signed / agent.lead_generated) * 100) 
// //                     : 0;
                
// //                 body += `
// //                     <tr>
// //                         <td>${agent.executive_name}</td>
// //                         <td>${agent.pseudo_name}</td>
// //                         <td class="text-center">${agent.lead_generated}</td>
                        
                        
// //                         <!-- Pending Approval -->
// //                         <td class="text-center">${agent.pending_approved}</td>
// //                         <td class="text-center">${pendingRatio}%</td>

// //                         <!-- Approved -->
// //                         <td class="text-center">${agent.approved}</td>
// //                         <td class="text-center">${approvalRatio}%</td>
                                                
// //                         <!-- Rejected -->
// //                         <td class="text-center">${agent.rejected}</td>
// //                         <td class="text-center">${agent.rejection_rate}%</td>
                        
// //                         <!-- Agreement Sent -->
// //                         <td class="text-center">${agent.agreement_sent}</td>
// //                         <td class="text-center">${agreementRatio}%</td>
                        
// //                         <!-- Signed -->
// //                         <td class="text-center">${agent.signed}</td>
// //                         <td class="text-center">${signedRatio}%</td>
// //                     </tr>`;
// //             });
            
// //             table.querySelector('tbody').innerHTML = body;
            
// //             // Calculate totals and ratios
// //             const totalApprovalRatio = data.totals.lead_generated > 0 
// //                 ? Math.round((data.totals.approved / data.totals.lead_generated) * 100) 
// //                 : 0;
            
// //             const totalPendingRatio = data.totals.lead_generated > 0 
// //                 ? Math.round((data.totals.pending_approved / data.totals.lead_generated) * 100) 
// //                 : 0;
            
// //             const totalAgreementRatio = data.totals.lead_generated > 0 
// //                 ? Math.round((data.totals.agreement_sent / data.totals.lead_generated) * 100) 
// //                 : 0;
            
// //             // Build footer
// //             const footer = `
// //                 <tr class="footer-row">
// //                     <th colspan="2">Total (${data.report_data.length} Agents)</th>
// //                     <th class="text-center">${data.totals.lead_generated}</th>
                    
// //                     <!-- Pending Approval Totals -->
// //                     <th class="text-center">${data.totals.pending_approved}</th>
// //                     <th class="text-center">${totalPendingRatio}%</th>

// //                            <!-- Approved Totals -->
// //                     <th class="text-center">${data.totals.approved}</th>
// //                     <th class="text-center">${totalApprovalRatio}%</th>
                    
// //                     <!-- Rejected Totals -->
// //                     <th class="text-center">${data.totals.rejected}</th>
// //                     <th class="text-center">${data.totals.rejection_rate}%</th>
                    
// //                     <!-- Agreement Sent Totals -->
// //                     <th class="text-center">${data.totals.agreement_sent}</th>
// //                     <th class="text-center">${totalAgreementRatio}%</th>
                    
// //                     <!-- Signed Totals -->
// //                     <th class="text-center">${data.totals.signed}</th>
// //                     <th class="text-center">${data.totals.signed_rate}%</th>
// //                 </tr>
// //                 <tr class="footer-notes">
// //                     <td colspan="14" class="text-center">
// //                         <strong>Month:</strong> ${data.month} | 
// //                         <strong>Approval Conversion:</strong> ${Math.round((data.totals.agreement_sent / data.totals.approved) * 100)}% | 
// //                         <strong>Signing Conversion:</strong> ${data.totals.agreement_conversion_rate}%
// //                     </td>
// //                 </tr>`;
            
// //             table.querySelector('tfoot').innerHTML = footer;
            
// //             applyConditionalFormatting();
// //         },
// //         error: function(error) {
// //             if (error.status === 403) {
// //                 frappe.msgprint("Authentication failed. Please login.");
// //             } else {
// //                 console.error("Error loading report:", error);
// //                 frappe.msgprint("Error loading data. Please try again.");
// //             }
// //         }
// //     });

// //     function applyConditionalFormatting() {
// //         const table = document.getElementById("bitcoinDepotTable");
// //         const rows = table.querySelectorAll('tbody tr');
        
// //         rows.forEach(row => {
// //             const cells = row.cells;
            
// //             // Highlight high performers (green)
// //             if (parseInt(cells[12].textContent) > 20) { // Signed ratio
// //                 cells[12].style.backgroundColor = "#e6f7e6";
// //             }
            
// //             // Highlight low performers (red)
// //             if (parseInt(cells[8].textContent) > 70) { // Rejection ratio
// //                 cells[8].style.backgroundColor = "#ffebeb";
// //             }
// //         });
// //     }
// // });
// // // frappe.ready(function() {
// // //     frappe.call({
// // //         method: "cclms.api.bitcoin_depot_report.get_bitcoin_depot_report",
// // //         callback: function(response) {
// // //             const data = response.message;
// // //             const table = document.getElementById("bitcoinDepotTable");
            
// // //             // Build header
// // //             const header = `
// // //                 <tr>
// // //                     <th style="min-width: 150px">Executive Name</th>
// // //                     <th style="min-width: 150px">Pseudo Name</th>
// // //                     <th style="min-width: 100px">Lead Generated</th>
// // //                     <th style="min-width: 120px">Total Approved Leads</th>
// // //                     <th style="min-width: 120px">Pending Approved Leads</th>
// // //                     <th style="min-width: 100px">Rejected Leads</th>
// // //                     <th style="min-width: 100px">Rejection Rate</th>
// // //                     <th style="min-width: 120px">Total Agreement Sent</th>
// // //                     <th style="min-width: 150px">Agreement Sent Not Signed</th>
// // //                     <th style="min-width: 100px">Total Signed</th>
// // //                     <th style="min-width: 100px">Signed Rate</th>
// // //                 </tr>`;
            
// // //             table.querySelector('thead').innerHTML = header;
            
// // //             // Build body
// // //             let body = '';
// // //             data.report_data.forEach(agent => {
// // //                 body += `
// // //                     <tr>
// // //                         <td>${agent.executive_name}</td>
// // //                         <td>${agent.pseudo_name}</td>
// // //                         <td class="text-center">${agent.lead_generated}</td>
// // //                         <td class="text-center">${agent.approved}</td>
// // //                         <td class="text-center">${agent.pending_approved}</td>
// // //                         <td class="text-center">${agent.rejected}</td>
// // //                         <td class="text-center">${agent.rejection_rate}%</td>
// // //                         <td class="text-center">${agent.agreement_sent}</td>
// // //                         <td class="text-center">${agent.agreement_not_signed}</td>
// // //                         <td class="text-center">${agent.signed}</td>
// // //                         <td class="text-center">${agent.signed_rate}%</td>
// // //                     </tr>`;
// // //             });
            
// // //             table.querySelector('tbody').innerHTML = body;
            
// // //             // Build footer
// // //             const footer = `
// // //                 <tr class="footer-row">
// // //                     <th colspan="2">Total (${data.report_data.length} Agents)</th>
// // //                     <th class="text-center">${data.totals.lead_generated}</th>
// // //                     <th class="text-center">${data.totals.approved}</th>
// // //                     <th class="text-center">${data.totals.pending_approved}</th>
// // //                     <th class="text-center">${data.totals.rejected}</th>
// // //                     <th class="text-center">${data.totals.rejection_rate}%</th>
// // //                     <th class="text-center">${data.totals.agreement_sent}</th>
// // //                     <th class="text-center">${data.totals.agreement_not_signed}</th>
// // //                     <th class="text-center">${data.totals.signed}</th>
// // //                     <th class="text-center">${data.totals.signed_rate}%</th>
// // //                 </tr>
// // //                 <tr class="footer-notes">
// // //                     <td colspan="12" class="text-center">
// // //                         <strong>Month:</strong> ${data.month} | 
// // //                         <strong>Approval Rate:</strong> ${100 - data.totals.rejection_rate}% | 
// // //                         <strong>Agreement Conversion:</strong> ${data.totals.agreement_conversion_rate}% (${data.totals.signed}/${data.totals.agreement_sent})
// // //                     </td>
// // //                 </tr>`;
            
// // //             table.querySelector('tfoot').innerHTML = footer;
            
// // //             // Apply conditional formatting
// // //             applyConditionalFormatting();
// // //         },
// // //         error: function(error) {
// // //             console.error("Error loading Bitcoin Depot report:", error);
// // //             frappe.msgprint("Error loading report data. Please try again.");
// // //         }
// // //     });

// // //     function applyConditionalFormatting() {
// // //         const table = document.getElementById("bitcoinDepotTable");
// // //         const rows = table.querySelectorAll('tbody tr');
        
// // //         rows.forEach(row => {
// // //             const cells = row.cells;
// // //             const rejectionRate = parseFloat(cells[6].textContent);
// // //             const signedRate = parseFloat(cells[10].textContent);
            
// // //             // Highlight high rejection rates
// // //             if (rejectionRate > 65) {
// // //                 cells[6].style.backgroundColor = "#ffdddd";
// // //             }
            
// // //             // Highlight good signed rates
// // //             if (signedRate > 20) {
// // //                 cells[10].style.backgroundColor = "#ddffdd";
// // //             }
// // //         });
// // //     }
// // // });