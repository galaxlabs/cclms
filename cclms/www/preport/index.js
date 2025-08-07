frappe.ready(function() {
    if (frappe.session.user === "Guest") {
        frappe.msgprint("Please login to view this report");
        return;
    }
    frappe.call({
        method: "cclms.api.bitcoin_depot_report.get_bitcoin_depot_report",
        callback: function(response) {
            const data = response.message;
            const table = document.getElementById("bitcoinDepotTable");
            
            // Build header with double rows
            const header = `
                <tr>
                    <th rowspan="2" style="min-width: 150px">Executive</th>
                    <th rowspan="2" style="min-width: 150px">Pseudo Name</th>
                    <th rowspan="2" style="min-width: 100px">Leads<br>Generated</th>
                    <th colspan="2" class="text-center">Pending Approval</th>
                    <th colspan="2" class="text-center">Approved</th>
                    <th colspan="2" class="text-center">Rejected</th>
                    <th colspan="2" class="text-center">Agreement Sent</th>
                    <th colspan="2" class="text-center">Signed</th>
                </tr>
                <tr>
                    <!-- Pending Approval Sub-headers -->
                    <th style="min-width: 80px">Count</th>
                    <th style="min-width: 80px">Ratio</th>

                    <!-- Approved Sub-headers -->
                    <th style="min-width: 80px">Count</th>
                    <th style="min-width: 80px">Ratio</th>
                    
                    <!-- Rejected Sub-headers -->
                    <th style="min-width: 80px">Count</th>
                    <th style="min-width: 80px">Ratio</th>
                    
                    <!-- Agreement Sent Sub-headers -->
                    <th style="min-width: 80px">Count</th>
                    <th style="min-width: 80px">Ratio</th>
                    
                    <!-- Signed Sub-headers -->
                    <th style="min-width: 80px">Count</th>
                    <th style="min-width: 80px">Ratio</th>
                </tr>`;
            
            table.querySelector('thead').innerHTML = header;
            
            // Build body
            let body = '';
            data.report_data.forEach(agent => {
                const approvalRatio = agent.lead_generated > 0 
                    ? Math.round((agent.approved / agent.lead_generated) * 100) 
                    : 0;
                
                const pendingRatio = agent.lead_generated > 0 
                    ? Math.round((agent.pending_approved / agent.lead_generated) * 100) 
                    : 0;
                
                const agreementRatio = agent.lead_generated > 0 
                    ? Math.round((agent.agreement_sent / agent.lead_generated) * 100) 
                    : 0;
                
                const signedRatio = agent.lead_generated > 0 
                    ? Math.round((agent.signed / agent.lead_generated) * 100) 
                    : 0;
                
                body += `
                    <tr>
                        <td>${agent.executive_name}</td>
                        <td>${agent.pseudo_name}</td>
                        <td class="text-center">${agent.lead_generated}</td>
                        
                        
                        <!-- Pending Approval -->
                        <td class="text-center">${agent.pending_approved}</td>
                        <td class="text-center">${pendingRatio}%</td>

                        <!-- Approved -->
                        <td class="text-center">${agent.approved}</td>
                        <td class="text-center">${approvalRatio}%</td>
                                                
                        <!-- Rejected -->
                        <td class="text-center">${agent.rejected}</td>
                        <td class="text-center">${agent.rejection_rate}%</td>
                        
                        <!-- Agreement Sent -->
                        <td class="text-center">${agent.agreement_sent}</td>
                        <td class="text-center">${agreementRatio}%</td>
                        
                        <!-- Signed -->
                        <td class="text-center">${agent.signed}</td>
                        <td class="text-center">${signedRatio}%</td>
                    </tr>`;
            });
            
            table.querySelector('tbody').innerHTML = body;
            
            // Calculate totals and ratios
            const totalApprovalRatio = data.totals.lead_generated > 0 
                ? Math.round((data.totals.approved / data.totals.lead_generated) * 100) 
                : 0;
            
            const totalPendingRatio = data.totals.lead_generated > 0 
                ? Math.round((data.totals.pending_approved / data.totals.lead_generated) * 100) 
                : 0;
            
            const totalAgreementRatio = data.totals.lead_generated > 0 
                ? Math.round((data.totals.agreement_sent / data.totals.lead_generated) * 100) 
                : 0;
            
            // Build footer
            const footer = `
                <tr class="footer-row">
                    <th colspan="2">Total (${data.report_data.length} Agents)</th>
                    <th class="text-center">${data.totals.lead_generated}</th>
                    
                    <!-- Pending Approval Totals -->
                    <th class="text-center">${data.totals.pending_approved}</th>
                    <th class="text-center">${totalPendingRatio}%</th>

                           <!-- Approved Totals -->
                    <th class="text-center">${data.totals.approved}</th>
                    <th class="text-center">${totalApprovalRatio}%</th>
                    
                    <!-- Rejected Totals -->
                    <th class="text-center">${data.totals.rejected}</th>
                    <th class="text-center">${data.totals.rejection_rate}%</th>
                    
                    <!-- Agreement Sent Totals -->
                    <th class="text-center">${data.totals.agreement_sent}</th>
                    <th class="text-center">${totalAgreementRatio}%</th>
                    
                    <!-- Signed Totals -->
                    <th class="text-center">${data.totals.signed}</th>
                    <th class="text-center">${data.totals.signed_rate}%</th>
                </tr>
                <tr class="footer-notes">
                    <td colspan="14" class="text-center">
                        <strong>Month:</strong> ${data.month} | 
                        <strong>Approval Conversion:</strong> ${Math.round((data.totals.agreement_sent / data.totals.approved) * 100)}% | 
                        <strong>Signing Conversion:</strong> ${data.totals.agreement_conversion_rate}%
                    </td>
                </tr>`;
            
            table.querySelector('tfoot').innerHTML = footer;
            
            applyConditionalFormatting();
        },
        error: function(error) {
            if (error.status === 403) {
                frappe.msgprint("Authentication failed. Please login.");
            } else {
                console.error("Error loading report:", error);
                frappe.msgprint("Error loading data. Please try again.");
            }
        }
    });

    function applyConditionalFormatting() {
        const table = document.getElementById("bitcoinDepotTable");
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const cells = row.cells;
            
            // Highlight high performers (green)
            if (parseInt(cells[12].textContent) > 20) { // Signed ratio
                cells[12].style.backgroundColor = "#e6f7e6";
            }
            
            // Highlight low performers (red)
            if (parseInt(cells[8].textContent) > 70) { // Rejection ratio
                cells[8].style.backgroundColor = "#ffebeb";
            }
        });
    }
});
// frappe.ready(function() {
//     frappe.call({
//         method: "cclms.api.bitcoin_depot_report.get_bitcoin_depot_report",
//         callback: function(response) {
//             const data = response.message;
//             const table = document.getElementById("bitcoinDepotTable");
            
//             // Build header
//             const header = `
//                 <tr>
//                     <th style="min-width: 150px">Executive Name</th>
//                     <th style="min-width: 150px">Pseudo Name</th>
//                     <th style="min-width: 100px">Lead Generated</th>
//                     <th style="min-width: 120px">Total Approved Leads</th>
//                     <th style="min-width: 120px">Pending Approved Leads</th>
//                     <th style="min-width: 100px">Rejected Leads</th>
//                     <th style="min-width: 100px">Rejection Rate</th>
//                     <th style="min-width: 120px">Total Agreement Sent</th>
//                     <th style="min-width: 150px">Agreement Sent Not Signed</th>
//                     <th style="min-width: 100px">Total Signed</th>
//                     <th style="min-width: 100px">Signed Rate</th>
//                 </tr>`;
            
//             table.querySelector('thead').innerHTML = header;
            
//             // Build body
//             let body = '';
//             data.report_data.forEach(agent => {
//                 body += `
//                     <tr>
//                         <td>${agent.executive_name}</td>
//                         <td>${agent.pseudo_name}</td>
//                         <td class="text-center">${agent.lead_generated}</td>
//                         <td class="text-center">${agent.approved}</td>
//                         <td class="text-center">${agent.pending_approved}</td>
//                         <td class="text-center">${agent.rejected}</td>
//                         <td class="text-center">${agent.rejection_rate}%</td>
//                         <td class="text-center">${agent.agreement_sent}</td>
//                         <td class="text-center">${agent.agreement_not_signed}</td>
//                         <td class="text-center">${agent.signed}</td>
//                         <td class="text-center">${agent.signed_rate}%</td>
//                     </tr>`;
//             });
            
//             table.querySelector('tbody').innerHTML = body;
            
//             // Build footer
//             const footer = `
//                 <tr class="footer-row">
//                     <th colspan="2">Total (${data.report_data.length} Agents)</th>
//                     <th class="text-center">${data.totals.lead_generated}</th>
//                     <th class="text-center">${data.totals.approved}</th>
//                     <th class="text-center">${data.totals.pending_approved}</th>
//                     <th class="text-center">${data.totals.rejected}</th>
//                     <th class="text-center">${data.totals.rejection_rate}%</th>
//                     <th class="text-center">${data.totals.agreement_sent}</th>
//                     <th class="text-center">${data.totals.agreement_not_signed}</th>
//                     <th class="text-center">${data.totals.signed}</th>
//                     <th class="text-center">${data.totals.signed_rate}%</th>
//                 </tr>
//                 <tr class="footer-notes">
//                     <td colspan="12" class="text-center">
//                         <strong>Month:</strong> ${data.month} | 
//                         <strong>Approval Rate:</strong> ${100 - data.totals.rejection_rate}% | 
//                         <strong>Agreement Conversion:</strong> ${data.totals.agreement_conversion_rate}% (${data.totals.signed}/${data.totals.agreement_sent})
//                     </td>
//                 </tr>`;
            
//             table.querySelector('tfoot').innerHTML = footer;
            
//             // Apply conditional formatting
//             applyConditionalFormatting();
//         },
//         error: function(error) {
//             console.error("Error loading Bitcoin Depot report:", error);
//             frappe.msgprint("Error loading report data. Please try again.");
//         }
//     });

//     function applyConditionalFormatting() {
//         const table = document.getElementById("bitcoinDepotTable");
//         const rows = table.querySelectorAll('tbody tr');
        
//         rows.forEach(row => {
//             const cells = row.cells;
//             const rejectionRate = parseFloat(cells[6].textContent);
//             const signedRate = parseFloat(cells[10].textContent);
            
//             // Highlight high rejection rates
//             if (rejectionRate > 65) {
//                 cells[6].style.backgroundColor = "#ffdddd";
//             }
            
//             // Highlight good signed rates
//             if (signedRate > 20) {
//                 cells[10].style.backgroundColor = "#ddffdd";
//             }
//         });
//     }
// });