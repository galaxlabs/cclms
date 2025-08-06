import frappe
from collections import defaultdict

def get_context(context):
    context.title = "Taskforce KPI Page"

# @frappe.whitelist()
# def get_kpi_data():
#     # Get all Operator Companies dynamically
#     companies = [c.name for c in frappe.get_all("Operator Companies")]

#     # Get all ATM Leads where executive_name is set
#     leads = frappe.get_all("ATM Leads", fields=["executive_name", "company"], filters={"executive_name": ["is", "set"]})

#     # Group leads by executive_name and count companies
#     agent_map = defaultdict(lambda: {
#         "signed": 0,
#         "companies": defaultdict(int)
#     })

#     for lead in leads:
#         exec_name = lead.executive_name
#         company = lead.company
#         agent_map[exec_name]["signed"] += 1
#         if company:
#             agent_map[exec_name]["companies"][company] += 1

#     # Now fetch pseudo name and full name from Sales Agent
#     data = []
#     for sales_agent_name, stats in agent_map.items():
#         sales_agent = frappe.get_value("Sales Agent",
#             sales_agent_name,
#             ["agent_name", "full_name"],
#             as_dict=True
#         )

#         row = {
#             "executive_name": sales_agent.full_name or "",
#             "agent_name": sales_agent.agent_name or "",
#             "signed": stats["signed"],
#             "companies": {},
#             "kpi_min": 10,  # Static or fetch later
#             "kpi_max": 13   # Static or fetch later
#         }

#         for company in companies:
#             row["companies"][company] = stats["companies"].get(company, 0)

#         data.append(row)

#     # Total counts per company
#     total_per_company = {c: 0 for c in companies}
#     for row in data:
#         for company in companies:
#             total_per_company[company] += row["companies"][company]

#     return {
#         "agents": data,
#         "companies": companies,
#         "totals": total_per_company
#     }
