frappe.ready(function() {
    frappe.call({
        method: "cclms.api.kpi_report.get_kpi_report_data",
        callback: function(response) {
            const data = response.message;
            const table = document.getElementById("kpiTable");
            
            // Build header
            let header = `
                <tr>
    
                    <th style="min-width: 155px; text-align: center;">Executive Name</th>
                    <th style="min-width: 130px; text-align: center;">Pseudo Name</th>
                    <th style="width: 80px; text-align: center;">Signed</th>`;
                    // <th>Executive Name</th>
                    // <th>Pseudo Name</th>
                    // <th>Signed</th>`;
            
            data.companies.forEach(company => {
                header += `<th style="min-width: 150px; text-align: center;">${company}</th>`;
            });
            
            header += `
                    <th style="width: 120px; text-align: center;">KPI Min</th>
                    <th style="width: 120px; text-align: center;">KPI Max</th>
                </tr>`;
            
            table.querySelector('thead').innerHTML = header;
            
            // Build body
            let body = '';
            data.executives.forEach(exec => {
                let row = `
                    <tr>
                        <td style="width: 120px; text-align: center;">${exec.executive_name}</td>
                        <td style="width: 120px; text-align: center;">${exec.pseudo_name}</td>
                        <td style="width: 80px; text-align: center;">${exec.signed || 0}</td>`;
                
                data.companies.forEach(company => {
                    row += `<td style="text-align: center;">${exec.company_counts[company] || 0}</td>`;
                });
                
                row += `
                        <td style="text-align: center;">${exec.kpi_minimum || '-'}</td>
                        <td style="text-align: center;">${exec.kpi_maximum || '-'}</td>
                    </tr>`;
                body += row;
            });
            
            table.querySelector('tbody').innerHTML = body;
            
            // Build footer
            let footer = `
                <tr>
                    <th colspan="2" style="text-align: center;">Total</th>
                    <th style="text-align: center;">${data.total_signed || 0}</th>`;
            
            data.companies.forEach(company => {
                footer += `<th style="text-align: center;">${data.company_totals[company] || 0}</th>`;
            });
            
            // Add KPI percentages (using first company's settings as example)
            const first_company = data.companies.length > 0 ? data.companies[0] : null;
            const min_percent = first_company ? (data.kpi_settings[first_company]?.min || 10) : 10;
            const max_percent = first_company ? (data.kpi_settings[first_company]?.max || 30) : 30;
            
            footer += `
                    <th style="text-align: center;">${min_percent}%</th>
                    <th style="text-align: center;">${max_percent}%</th>
                </tr>`;
            
            table.querySelector('tfoot').innerHTML = footer;
        },
        error: function(error) {
            console.error("Error loading KPI report:", error);
            frappe.msgprint("Error loading KPI report data. Please try again.");
        }
    });
});
// frappe.ready(function() {
//     frappe.call({
//         method: "cclms.api.kpi_report.get_kpi_report_data",
//         callback: function(response) {
//             const data = response.message;
//             const table = document.getElementById("kpiTable");
            
//             // Build header
//             let header = `<tr>
//                 <th>Executive Name</th>
//                 <th>Pseudo Name</th>
//                 <th>Signed</th>`;
            
//             data.companies.forEach(company => {
//                 header += `<th>${company}</th>`;
//             });
            
//             header += `<th>KPI Minimum</th>
//                 <th>KPI Maximum</th>
//             </tr>`;
            
//             table.querySelector('thead').innerHTML = header;
            
//             // Build body
//             let body = '';
//             data.executives.forEach(exec => {
//                 let row = `<tr>
//                     <td>${exec.executive_name}</td>
//                     <td>${exec.pseudo_name}</td>
//                     <td>${exec.signed}</td>`;
                
//                 data.companies.forEach(company => {
//                     row += `<td>${exec.company_counts[company] || ''}</td>`;
//                 });
                
//                 row += `<td>${exec.kpi_minimum}</td>
//                     <td>${exec.kpi_maximum}</td>
//                 </tr>`;
//                 body += row;
//             });
            
//             table.querySelector('tbody').innerHTML = body;
            
//             // Build footer
//             let footer = `<tr>
//                 <th colspan="2">Total</th>
//                 <th>${data.total_signed}</th>`;
            
//             data.companies.forEach(company => {
//                 footer += `<th>${data.totals[company]}</th>`;
//             });
            
//             // Add KPI percentages (assuming first company's settings for demo)
//             const firstCompany = data.companies[0];
//             footer += `<th>${data.kpi_settings[firstCompany]?.min || '10'}%</th>
//                 <th>${data.kpi_settings[firstCompany]?.max || '30'}%</th>
//             </tr>`;
            
//             table.querySelector('tfoot').innerHTML = footer;
//         },
//         error: function(error) {
//             console.error("Error:", error);
//             frappe.msgprint("Error loading data");
//         }
//     });
// });
// double header 
// frappe.ready(function () {
//     frappe.call({
//         method: "cclms.api.kpi_report.get_kpi_report_data",
//         callback: function(response) {
//             const reportData = response.message.report_data;
//             const totalSigned = response.message.total_signed;
//             const kpiPercentage = response.message.kpi_percentage;

//             let tableBody = '';
//             let footerRow = `<tr><th>Total</th><td></td><td><b>${totalSigned}</b></td>`;

//             // Create the headers dynamically for each company
//             let headerRow = `<tr><th>Executive Name</th><th>Pseudo Name</th><th>Signed</th>`;
//             let kpiHeaderRow = `<tr><th>KPI Min</th><th>KPI Max</th>`;

//             // Iterate through companies and create column data
//             reportData.forEach(companyData => {
//                 headerRow += `<th>${companyData.company}</th>`;
//                 kpiHeaderRow += `<th>${companyData.company}</th>`;

//                 tableBody += `
//                     <tr>
//                         <td rowspan="${companyData.agents.length + 1}">${companyData.company}</td>
//                 `;

//                 // Render each agent in the company
//                 companyData.agents.forEach(agent => {
//                     tableBody += `
//                         <td>${agent.full_name}</td>
//                         <td>${agent.pseudo_name}</td>
//                         <td>${agent.signed}</td>
//                         <td>${agent.kpi_minimum}</td>
//                         <td>${agent.kpi_maximum}</td>
//                     </tr>
//                     `;
//                 });

//                 footerRow += `<td><b>${companyData.company_total}</b></td>`;
//             });

//             footerRow += `<td><b>${kpiPercentage.min_percentage}%</b></td><td><b>${kpiPercentage.max_percentage}%</b></td></tr>`;

//             // Insert the rows and totals into the table
//             const table = document.getElementById("kpiTable");
//             table.querySelector('thead').innerHTML = headerRow + kpiHeaderRow;
//             table.querySelector('tbody').innerHTML = tableBody;
//             table.querySelector('tfoot').innerHTML = footerRow;
//         },
//         error: function(error) {
//             console.error("Error fetching data:", error);
//             frappe.msgprint("There was an issue fetching the data. Please try again.");
//         }
//     });
// });
// wrong layout
// frappe.ready(function () {
//     frappe.call({
//         method: "cclms.api.kpi_report.get_kpi_report_data",
//         callback: function(response) {
//             const reportData = response.message.report_data;
//             const totalSigned = response.message.total_signed;
//             const kpiPercentage = response.message.kpi_percentage;

//             let tableBody = '';
//             let footerRow = `<tr><th>Total</th><td></td><td><b>${totalSigned}</b></td>`;

//             reportData.forEach(companyData => {
//                 tableBody += `
//                     <tr>
//                         <td rowspan="${companyData.agents.length + 1}">${companyData.company}</td>
//                 `;

//                 // Render each agent in the company
//                 companyData.agents.forEach(agent => {
//                     tableBody += `
//                         <td>${agent.full_name}</td>
//                         <td>${agent.pseudo_name}</td>
//                         <td>${agent.signed}</td>
//                         <td>${agent.kpi_minimum}</td>
//                         <td>${agent.kpi_maximum}</td>
//                     </tr>
//                     `;
//                 });

//                 footerRow += `<td><b>${companyData.company_total}</b></td>`;
//             });

//             footerRow += `<td><b>${kpiPercentage.min_percentage}%</b></td><td><b>${kpiPercentage.max_percentage}%</b></td></tr>`;

//             // Insert the rows and totals into the table
//             const table = document.getElementById("kpiTable");
//             table.querySelector('tbody').innerHTML = tableBody;
//             table.querySelector('tfoot').innerHTML = footerRow;
//         },
//         error: function(error) {
//             console.error("Error fetching data:", error);
//             frappe.msgprint("There was an issue fetching the data. Please try again.");
//         }
//     });
// });


// frappe.ready(function() {
//   // Function to fetch data
//   function fetchData(apiMethod) {
//       frappe.call({
//           method: apiMethod,
//           callback: function(response) {
//               if (response.message) {
//                   console.log(response.message);  // Output data to console for now
//                   // Process the data and update your UI accordingly
//               } else {
//                   frappe.msgprint(__('No data found.'));
//               }
//           },
//           error: function(error) {
//               frappe.msgprint(__('Error fetching data.'));
//               console.log(error);
//           }
//       });
//   }

//   // Fetch data for ATM Leads, Sales Agents, Operator Companies, and Branch KPI Settings
//   fetchData("cclms.api.kpi_report.get_atm_leads_data");
//   fetchData("cclms.api.kpi_report.get_sales_agent_data");
//   fetchData("cclms.api.kpi_report.get_operator_companies_data");
//   fetchData("cclms.api.kpi_report.get_branch_kpi_settings_data");
//   fetchData("cclms.api.kpi_report.get_workflow_data");
  

// });

// // Fetch and display data for ATM Leads, Sales Agents, Operator Companies, Branch KPI Settings

// frappe.ready(function () {
//   // Function to get data
//   function fetchData(apiMethod) {
//       frappe.call({
//           method: apiMethod,
//           callback: function(response) {
//               if (response.message) {
//                   const data = response.message;
//                   console.log(data); // Output data to console for now

//                   // Add dynamic rendering logic here to display data in the UI
//               } else {
//                   frappe.msgprint(__('No data found.'));
//               }
//           },
//           error: function(error) {
//               frappe.msgprint(__('Error fetching data.'));
//               console.log(error);
//           }
//       });
//   }

//   // Fetch data for ATM Leads, Sales Agents, Operator Companies, and Branch KPI Settings
//   fetchData("cclms.api.kpi_report.get_atm_leads_data");
//   fetchData("cclms.api.kpi_report.get_sales_agent_data");
//   fetchData("cclms.api.kpi_report.get_operator_companies_data");
//   fetchData("cclms.api.kpi_report.get_branch_kpi_settings_data");

//   // Example: Updating data for ATM Leads (this would be triggered by a UI action, e.g., button click)
//   function updateLeadData(leadName, kpiMin, kpiMax) {
//       frappe.call({
//           method: "cclms.api.kpi_report.update_atm_lead_data",
//           args: {
//               lead_name: leadName,
//               kpi_min: kpiMin,
//               kpi_max: kpiMax
//           },
//           callback: function(response) {
//               if (response.message.status === "success") {
//                   frappe.msgprint(response.message.message);
//               } else {
//                   frappe.msgprint(response.message.message);
//               }
//           },
//           error: function(error) {
//               frappe.msgprint(__('Error updating data.'));
//           }
//       });
//   }

//   // Example of update
//   updateLeadData("ATMLead123", 10, 15);
// });
