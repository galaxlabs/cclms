import frappe
from frappe import _
from frappe.utils import getdate, nowdate, getdate, get_first_day, get_last_day
from datetime import datetime, timedelta



# Fetch data for ATM Leads
# @frappe.whitelist(allow_guest=True)
# def get_atm_leads_data():

#     current_month_start = get_first_day(datetime.today())
#     current_month_end = get_last_day(datetime.today())
    
#     leads = frappe.get_all(
#         "ATM Leads",
#         filters={
#             "workflow_state": "Signed",
#             "sign_date": [">=", current_month_start],
#             "sign_date": ["<=", current_month_end]
#         },
#         fields=["executive_name", "company", "workflow_state", "sign_date", "kpi_min", "kpi_max"]
#     )



#     """
#     Fetch all ATM leads with required fields
#     """
#     leads = frappe.get_all(
#         "ATM Leads", 
#         fields=["name", "executive_name", "company", "workflow_state", "kpi_min", "kpi_max", "sign_date", "agreement_sent_date", "approve_date", "branch"]
#     )
#     return {"leads": leads}

# @frappe.whitelist(allow_guest=True)
# def get_sales_agent_data():
#     """
#     Fetch all Sales Agent data
#     """
#     agents = frappe.get_all(
#         "Sales Agent", 
#         fields=["agent_name", "full_name", "kpi_minimum", "kpi_maximum"]
#     )
#     return {"agents": agents}

# @frappe.whitelist(allow_guest=True)
# def get_operator_companies_data():
#     """
#     Fetch all Operator Companies data
#     """
#     companies = frappe.get_all(
#         "Operator Companies", 
#         fields=["name"]
#     )
#     return {"companies": companies}

# @frappe.whitelist(allow_guest=True)
# def get_branch_kpi_settings_data():
#     """
#     Fetch all Branch KPI Settings data
#     """
#     kpi_settings = frappe.get_all(
#         "Branch KPI Settings", 
#         fields=["branch", "kpi_min_percentage", "kpi_max_percentage"]
#     )
#     return {"kpi_settings": kpi_settings}

# @frappe.whitelist(allow_guest=True)
# def get_workflow_data():
#     """
#     Fetch all Branch KPI Settings data
#     """
#     workflow_state = frappe.get_all(
#         "Workflow State", 
#         fields=["workflow_state_name"]
#     )
#     return {"workflow_state_name": workflow_state}

##################1
# @frappe.whitelist(allow_guest=True)
# def get_kpi_report_data():
#     # Get the start and end of the current month
#     current_month_start = get_first_day(datetime.today())
#     current_month_end = get_last_day(datetime.today())
    
#     # Fetch ATM Leads for this month with 'Signed' workflow_state
#     leads = frappe.get_all(
#         "ATM Leads", 
#         filters={
#             "workflow_state": "Signed",
#             "sign_date": [">=", current_month_start],
#             "sign_date": ["<=", current_month_end]
#         },
#         fields=["executive_name", "company", "workflow_state", "sign_date", "kpi_min", "kpi_max"]
#     )

#     # Fetch Sales Agent data (executive_name, full_name, kpi_minimum, kpi_maximum)
#     agents = frappe.get_all(
#         "Sales Agent", 
#         fields=["agent_name", "full_name", "kpi_minimum", "kpi_maximum"]
#     )
    
#     # Fetch Operator Companies data
#     companies = frappe.get_all(
#         "Operator Companies", 
#         fields=["name"]
#     )
    
#     # Fetch Branch KPI Settings to calculate KPI percentage
#     kpi_settings = frappe.get_all(
#         "Branch KPI Settings", 
#         fields=["branch", "kpi_min_percentage", "kpi_max_percentage"]
#     )
    
#     # Map executive_name to their full_name and KPI values
#     agent_map = {agent["agent_name"]: agent for agent in agents}
    
#     # Initialize company map
#     company_map = {company["name"]: {"signed": 0, "agents": {}} for company in companies}
    
#     # Process each lead to link executive_name with agent data
#     for lead in leads:
#         company_name = lead.get("company", "Unknown")
#         executive_name = lead.get("executive_name", "Unknown")

#         # Initialize company in the map if not already initialized
#         if company_name not in company_map:
#             company_map[company_name] = {"signed": 0, "agents": {}}

#         # Initialize agent in the company if not already initialized
#         if executive_name not in company_map[company_name]["agents"]:
#             company_map[company_name]["agents"][executive_name] = {
#                 "signed": 0, "full_name": "", "kpi_minimum": 10, "kpi_maximum": 13
#             }

#         # Increment the signed lead count for the agent and company
#         company_map[company_name]["agents"][executive_name]["signed"] += 1
#         company_map[company_name]["signed"] += 1
        
#         # Get agent data from the agent_map
#         agent_data = agent_map.get(executive_name)
#         if agent_data:
#             company_map[company_name]["agents"][executive_name]["full_name"] = agent_data.get("full_name", "")
#             company_map[company_name]["agents"][executive_name]["kpi_minimum"] = agent_data.get("kpi_minimum", 10)
#             company_map[company_name]["agents"][executive_name]["kpi_maximum"] = agent_data.get("kpi_maximum", 13)
    
#     # Prepare report data with KPI percentages
#     report_data = []
#     total_signed = 0
#     for company, data in company_map.items():
#         row_data = {
#             "company": company,
#             "agents": []
#         }

#         company_total = 0
#         for agent_name, agent_data in data["agents"].items():
#             row_data["agents"].append({
#                 "full_name": agent_data["full_name"],  # Full name from Sales Agent
#                 "pseudo_name": agent_name,             # Executive Name as Pseudo Name
#                 "signed": agent_data["signed"],
#                 "kpi_minimum": agent_data["kpi_minimum"],
#                 "kpi_maximum": agent_data["kpi_maximum"]
#             })
#             company_total += agent_data["signed"]

#         total_signed += company_total
#         row_data["company_total"] = company_total
#         report_data.append(row_data)

#     # Step 9: Calculate KPI percentage for each company from the Branch KPI Settings
#     kpi_percentage = {}
#     for company in company_map:
#         kpi_percentage[company] = {
#             "min_percentage": 0,
#             "max_percentage": 0
#         }
#         # Example: Assuming KPI settings are linked by company name (adjust as needed)
#         kpi_setting = next((setting for setting in kpi_settings if setting["branch"] == company), None)
#         if kpi_setting:
#             kpi_percentage[company]["min_percentage"] = kpi_setting.get("kpi_min_percentage", 10)
#             kpi_percentage[company]["max_percentage"] = kpi_setting.get("kpi_max_percentage", 30)

#     return {
#         "report_data": report_data,
#         "total_signed": total_signed,
#         "kpi_percentage": kpi_percentage
#     }

# # Helper functions to get the start and end of the current month
# def get_first_day(date):
#     return date.replace(day=1)

# def get_last_day(date):
#     next_month = date.replace(day=28) + timedelta(days=4)  # this will always land in the next month
#     return next_month - timedelta(days=next_month.day)
####################### dobule header 

# @frappe.whitelist(allow_guest=True)
# def get_kpi_report_data():
#     # Get the start and end of the current month
#     current_month_start = get_first_day(datetime.today())
#     current_month_end = get_last_day(datetime.today())
    
#     # Fetch ATM Leads for this month with 'Signed' workflow_state
#     leads = frappe.get_all(
#         "ATM Leads", 
#         filters={
#             "workflow_state": "Signed",
#             "sign_date": [">=", current_month_start],
#             "sign_date": ["<=", current_month_end]
#         },
#         fields=["executive_name", "company", "workflow_state", "sign_date", "kpi_min", "kpi_max"]
#     )

#     # Fetch Sales Agent data (executive_name, full_name, kpi_minimum, kpi_maximum)
#     agents = frappe.get_all(
#         "Sales Agent", 
#         fields=["agent_name", "full_name", "kpi_minimum", "kpi_maximum"]
#     )
    
#     # Fetch Operator Companies data
#     companies = frappe.get_all(
#         "Operator Companies", 
#         fields=["name"]
#     )
    
#     # Fetch Branch KPI Settings to calculate KPI percentage
#     kpi_settings = frappe.get_all(
#         "Branch KPI Settings", 
#         fields=["branch", "kpi_min_percentage", "kpi_max_percentage"]
#     )
    
#     # Map executive_name to their full_name and KPI values
#     agent_map = {agent["agent_name"]: agent for agent in agents}
    
#     # Initialize company map to hold signed count for each company
#     company_map = {company["name"]: {"signed": 0, "agents": {}} for company in companies}
    
#     # Process each lead to link executive_name with agent data
#     for lead in leads:
#         company_name = lead.get("company", "Unknown")
#         executive_name = lead.get("executive_name", "Unknown")

#         # Initialize company in the map if not already initialized
#         if company_name not in company_map:
#             company_map[company_name] = {"signed": 0, "agents": {}}

#         # Initialize agent in the company if not already initialized
#         if executive_name not in company_map[company_name]["agents"]:
#             company_map[company_name]["agents"][executive_name] = {
#                 "signed": 0, "full_name": "", "kpi_minimum": 10, "kpi_maximum": 13
#             }

#         # Increment the signed lead count for the agent and company
#         company_map[company_name]["agents"][executive_name]["signed"] += 1
#         company_map[company_name]["signed"] += 1
        
#         # Get agent data from the agent_map
#         agent_data = agent_map.get(executive_name)
#         if agent_data:
#             company_map[company_name]["agents"][executive_name]["full_name"] = agent_data.get("full_name", "")
#             company_map[company_name]["agents"][executive_name]["kpi_minimum"] = agent_data.get("kpi_minimum", 10)
#             company_map[company_name]["agents"][executive_name]["kpi_maximum"] = agent_data.get("kpi_maximum", 13)
    
#     # Prepare report data with KPI percentages
#     report_data = []
#     total_signed = 0
#     for company, data in company_map.items():
#         row_data = {
#             "company": company,
#             "agents": []
#         }

#         company_total = 0
#         for agent_name, agent_data in data["agents"].items():
#             row_data["agents"].append({
#                 "full_name": agent_data["full_name"],  # Full name from Sales Agent
#                 "pseudo_name": agent_name,             # Executive Name as Pseudo Name
#                 "signed": agent_data["signed"],
#                 "kpi_minimum": agent_data["kpi_minimum"],
#                 "kpi_maximum": agent_data["kpi_maximum"]
#             })
#             company_total += agent_data["signed"]

#         total_signed += company_total
#         row_data["company_total"] = company_total
#         report_data.append(row_data)

#     # Step 9: Calculate KPI percentage for each company from the Branch KPI Settings
#     kpi_percentage = {}
#     for company in company_map:
#         kpi_percentage[company] = {
#             "min_percentage": 0,
#             "max_percentage": 0
#         }
#         # Example: Assuming KPI settings are linked by company name (adjust as needed)
#         kpi_setting = next((setting for setting in kpi_settings if setting["branch"] == company), None)
#         if kpi_setting:
#             kpi_percentage[company]["min_percentage"] = kpi_setting.get("kpi_min_percentage", 10)
#             kpi_percentage[company]["max_percentage"] = kpi_setting.get("kpi_max_percentage", 30)

#     return {
#         "report_data": report_data,
#         "total_signed": total_signed,
#         "kpi_percentage": kpi_percentage
#     }

# # Helper functions to get the start and end of the current month
# def get_first_day(date):
#     return date.replace(day=1)

# def get_last_day(date):
#     next_month = date.replace(day=28) + timedelta(days=4)  # this will always land in the next month
#     return next_month - timedelta(days=next_month.day)
# ###############not work
# @frappe.whitelist(allow_guest=True)
# def get_kpi_report_data():
#     # Get the start and end of the current month
#     current_month_start = get_first_day(datetime.today())
#     current_month_end = get_last_day(datetime.today())
    
#     # Fetch ATM Leads for this month with 'Signed' workflow_state
#     leads = frappe.get_all(
#         "ATM Leads", 
#         filters={
#             "workflow_state": "Signed",
#             "sign_date": [">=", current_month_start],
#             "sign_date": ["<=", current_month_end]
#         },
#         fields=["executive_name", "company", "workflow_state", "sign_date", "kpi_min", "kpi_max"]
#     )

#     # Fetch Sales Agent data (executive_name, full_name, kpi_minimum, kpi_maximum)
#     agents = frappe.get_all(
#         "Sales Agent", 
#         fields=["full_name as executive_name", "agent_name as pseudo_name", 
#                "kpi_minimum", "kpi_maximum"]
#     )
    
#     # Fetch Operator Companies data
#     companies = frappe.get_all(
#         "Operator Companies", 
#         fields=["name"]
#     )
    
#     result = {
#     "executives": [],
#     "companies": [c["name"] for c in companies],
#     "totals": {c["name"]: 0 for c in companies},
#     "kpi_settings": {}
#     }
    
#     for setting in frappe.get_all("Branch KPI Settings", 
#             fields=["branch", "kpi_min_percentage", "kpi_max_percentage"]):
#         result["kpi_settings"][setting["branch"]] = {
#         "min": setting["kpi_min_percentage"],
#         "max": setting["kpi_max_percentage"]
#     }
#     # Fetch Branch KPI Settings to calculate KPI percentage
    
#     # kpi_settings = frappe.get_all(
#     #     "Branch KPI Settings", 
#     #     fields=["branch", "kpi_min_percentage", "kpi_max_percentage"]
#     # )
    
#     # Map executive_name to their full_name and KPI values
    
#     for agent in agents:
#         executive = {
#             "executive_name": agent["executive_name"],
#             "pseudo_name": agent["pseudo_name"],
#             "signed": 0,
#             "company_counts": {c: 0 for c in result["companies"]},
#             "kpi_minimum": agent["kpi_minimum"],
#             "kpi_maximum": agent["kpi_maximum"]
#         }
#         result["executives"].append(executive)
    
#     # Initialize company map to hold signed count for each company
    
    
    
#     # Process each lead to link executive_name with agent data
#     for lead in frappe.get_all("ATM Leads", 
#                              filters={
#                                  "workflow_state": "Signed",
#                                  "sign_date": [">=", current_month_start],
#                                  "sign_date": ["<=", current_month_end]
#                              },
#                              fields=["executive_name", "company"]):
#         # Find executive and update counts
#         for exec in result["executives"]:
#             if exec["executive_name"] == lead["executive_name"]:
#                 exec["company_counts"][lead["company"]] += 1
#                 exec["signed"] += 1
#                 result["totals"][lead["company"]] += 1
#                 break
    
#     result["total_signed"] = sum(result["totals"].values())
#     return result    
#         # Get agent data from the agent_map

# # Helper functions to get the start and end of the current month
# def get_first_day(date):
#     return date.replace(day=1)

# def get_last_day(date):
#     next_month = date.replace(day=28) + timedelta(days=4)  # this will always land in the next month
#     return next_month - timedelta(days=next_month.day)

from datetime import datetime, timedelta
import frappe

def get_first_day(date):
    return date.replace(day=1)

def get_last_day(date):
    next_month = date.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)

@frappe.whitelist(allow_guest=True)
def get_kpi_report_data():
    # Get date range for current month
    current_month_start = get_first_day(datetime.today())
    current_month_end = get_last_day(datetime.today())
    
    # Get all sales agents
    agents = frappe.get_all(
        "Sales Agent",
        fields=["name as executive_name", "full_name as pseudo_name", 
                "kpi_minimum", "kpi_maximum"]
    )
    
    # Get all operator companies
    companies = frappe.get_all("Operator Companies", fields=["name"])
    company_names = [c["name"] for c in companies]
    
    # Get KPI settings
    kpi_settings = {}
    for setting in frappe.get_all("Branch KPI Settings",
                                fields=["branch", "kpi_min_percentage", "kpi_max_percentage"]):
        kpi_settings[setting["branch"]] = {
            "min": setting["kpi_min_percentage"],
            "max": setting["kpi_max_percentage"]
        }
    
    # Initialize executive data
    executives = []
    company_totals = {company: 0 for company in company_names}
    total_signed = 0
    
    for agent in agents:
        executive = {
            "executive_name": agent["executive_name"],
            "pseudo_name": agent["pseudo_name"],
            "signed": 0,
            "company_counts": {company: 0 for company in company_names},
            "kpi_minimum": agent["kpi_minimum"],
            "kpi_maximum": agent["kpi_maximum"]
        }
        executives.append(executive)
    
    # Get all signed leads for current month
    leads = frappe.get_all(
        "ATM Leads",
        filters={
            "workflow_state": "Signed",
            "sign_date": [">=", current_month_start],
            "sign_date": ["<=", current_month_end]
        },
        fields=["executive_name", "company"]
    )
    
    # Process leads and count by executive and company
    for lead in leads:
        for executive in executives:
            if executive["executive_name"] == lead["executive_name"]:
                if lead["company"] in executive["company_counts"]:
                    executive["company_counts"][lead["company"]] += 1
                    executive["signed"] += 1
                    company_totals[lead["company"]] += 1
                    total_signed += 1
                break
    
    return {
        "executives": executives,
        "companies": company_names,
        "company_totals": company_totals,
        "total_signed": total_signed,
        "kpi_settings": kpi_settings
    }