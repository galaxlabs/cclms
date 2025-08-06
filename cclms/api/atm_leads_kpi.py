
# import frappe
# from datetime import datetime

# @frappe.whitelist()
# def get_monthly_sign_counts_by_company():
#     from frappe.utils import get_first_day, get_last_day

#     # Get first and last day of current month
#     today = datetime.today()
#     first_day = get_first_day(today)
#     last_day = get_last_day(today)

#     # Get all ATM Leads signed this month
#     leads = frappe.get_all(
#         "ATM Leads",
#         fields=["company", "sign_date"],
#         filters={
#             "sign_date": ["between", [first_day, last_day]],
#             "docstatus": ["<", 2]
#         }
#     )

#     # Count grouped by company
#     company_counts = {}

#     for lead in leads:
#         company = lead.company or "Unknown"
#         if company not in company_counts:
#             company_counts[company] = 0
#         company_counts[company] += 1

#     return company_counts

# import frappe
# from frappe.utils import get_first_day, get_last_day
# from datetime import datetime
# import calendar
# from collections import defaultdict

# @frappe.whitelist()
# def get_monthly_leads_table(month=None, year=None):
#     if not month or not year:
#         return {"error": "Month and Year are required."}

#     try:
#         month = int(month)
#         year = int(year)
#         start_date = datetime(year, month, 1).date()
#         end_date = datetime(year, month, calendar.monthrange(year, month)[1]).date()
#     except:
#         return {"error": "Invalid date provided."}

#     # Fetch leads
#     leads = frappe.get_all(
#         "ATM Leads",
#         filters={"sign_date": ["between", [start_date, end_date]]},
#         fields=["executive_name", "company"]
#     )

#     # Fetch executive info and group by agent
#     data = {}
#     companies = set()

#     for lead in leads:
#         exec_id = lead.get("executive_name")
#         company = lead.get("company")
#         companies.add(company)

#         if not exec_id:
#             continue

#         try:
#             agent = frappe.get_doc("Sales Agent", exec_id)
#             exec_name = agent.get("sales_agent_name") or agent.get("full_name") or exec_id
#             pseudo = agent.get("agent_name") or "-"
#             kpi_min = agent.get("kpi_minimum") or "-"
#             kpi_max = agent.get("kpi_maximum") or "-"
#         except:
#             exec_name = exec_id
#             pseudo = "-"
#             kpi_min = "-"
#             kpi_max = "-"

#         key = exec_id
#         if key not in data:
#             data[key] = {
#                 "executive_name": exec_name,
#                 "pseudo_name": pseudo,
#                 "kpi_min": kpi_min,
#                 "kpi_max": kpi_max,
#                 "companies": defaultdict(int)
#             }

#         data[key]["companies"][company] += 1

#     return {
#         "rows": list(data.values()),
#         "companies": sorted(list(companies))
#     }
