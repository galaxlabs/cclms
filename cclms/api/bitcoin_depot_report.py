from datetime import datetime, timedelta
import frappe

def get_first_day(date):
    return date.replace(day=1)

def get_last_day(date):
    next_month = date.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)

@frappe.whitelist()
def get_bitcoin_depot_report():
    # Check user permissions
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)
    
    current_month_start = get_first_day(datetime.today())
    current_month_end = get_last_day(datetime.today())
    
    # Get sales agents (filtered by user permissions)
    agents = frappe.get_all(
        "Sales Agent",
        fields=["full_name as executive_name", "agent_name as pseudo_name"],
        filters={}  # Add any permission filters here if needed
    )
    
    # Initialize data structure
    report_data = []
    totals = {
        "lead_generated": 0,
        "approved": 0,
        "pending_approved": 0,
        "rejected": 0,
        "agreement_sent": 0,
        "agreement_not_signed": 0,
        "signed": 0
    }
    
    for agent in agents:
        # Get all leads for this agent in Bitcoin Depot
        # Filter by: 
        # - Current month creation OR update
        # - Company is Bitcoin Depot
        # - Not in Draft state
        leads = frappe.get_all(
            "ATM Leads",
            filters=[
                ["executive_name", "=", agent["executive_name"]],
                ["company", "=", "Bitcoin Depot"],
                ["workflow_state", "!=", "Draft"]
            ],
            or_filters=[
                ["creation", "between", [current_month_start, current_month_end]],
                ["modified", "between", [current_month_start, current_month_end]]
            ],
            fields=["name", "workflow_state", "creation", "modified"]
        )
        
        lead_count = len(leads)
        if lead_count == 0:
            continue
        
        # Initialize agent counts
        agent_data = {
            "executive_name": agent["executive_name"],
            "pseudo_name": agent["pseudo_name"],
            "lead_generated": lead_count,
            "approved": 0,
            "pending_approved": 0,
            "rejected": 0,
            "agreement_sent": 0,
            "agreement_not_signed": 0,
            "signed": 0,
            "last_updated": None
        }
        
        # Count statuses
        for lead in leads:
            status = (lead.workflow_state or "").lower()
            
            if "approved" in status:
                if "pending" in status:
                    agent_data["pending_approved"] += 1
                else:
                    agent_data["approved"] += 1
            elif "rejected" in status:
                agent_data["rejected"] += 1
            elif "agreement sent" in status or "agreement_sent" in status:
                agent_data["agreement_sent"] += 1
                if "signed" not in status:
                    agent_data["agreement_not_signed"] += 1
            elif "signed" in status:
                agent_data["signed"] += 1
            
            # Track latest update time
            if not agent_data["last_updated"] or lead.modified > agent_data["last_updated"]:
                agent_data["last_updated"] = lead.modified
        
        # Calculate percentages
        agent_data["rejection_rate"] = round((agent_data["rejected"] / agent_data["lead_generated"]) * 100, 2) if agent_data["lead_generated"] > 0 else 0
        agent_data["signed_rate"] = round((agent_data["signed"] / agent_data["lead_generated"]) * 100, 2) if agent_data["lead_generated"] > 0 else 0
        
        report_data.append(agent_data)
        
        # Update totals
        totals["lead_generated"] += agent_data["lead_generated"]
        totals["approved"] += agent_data["approved"]
        totals["pending_approved"] += agent_data["pending_approved"]
        totals["rejected"] += agent_data["rejected"]
        totals["agreement_sent"] += agent_data["agreement_sent"]
        totals["agreement_not_signed"] += agent_data["agreement_not_signed"]
        totals["signed"] += agent_data["signed"]
    
    # Calculate overall percentages
    totals["rejection_rate"] = round((totals["rejected"] / totals["lead_generated"]) * 100, 2) if totals["lead_generated"] > 0 else 0
    totals["signed_rate"] = round((totals["signed"] / totals["lead_generated"]) * 100, 2) if totals["lead_generated"] > 0 else 0
    totals["agreement_conversion_rate"] = round((totals["signed"] / totals["agreement_sent"]) * 100, 2) if totals["agreement_sent"] > 0 else 0
    
    # Sort by most recently updated agent
    report_data.sort(key=lambda x: x["last_updated"] or "", reverse=True)
    
    return {
        "report_data": report_data,
        "totals": totals,
        "month": current_month_start.strftime("%B %Y"),
        "date_range": f"{current_month_start.strftime('%Y-%m-%d')} to {current_month_end.strftime('%Y-%m-%d')}"
    }
# from datetime import datetime, timedelta
# import frappe

# def get_first_day(date):
#     return date.replace(day=1)

# def get_last_day(date):
#     next_month = date.replace(day=28) + timedelta(days=4)
#     return next_month - timedelta(days=next_month.day)

# @frappe.whitelist(allow_guest=True)
# def get_bitcoin_depot_report():
#     current_month_start = get_first_day(datetime.today())
#     current_month_end = get_last_day(datetime.today())
    
#     # Get all sales agents
#     agents = frappe.get_all(
#         "Sales Agent",
#         fields=["full_name as executive_name", "agent_name as pseudo_name"]
#     )
    
#     # Initialize data structure
#     report_data = []
#     totals = {
#         "lead_generated": 0,
#         "approved": 0,
#         "pending_approved": 0,
#         "rejected": 0,
#         "agreement_sent": 0,
#         "agreement_not_signed": 0,
#         "signed": 0
#     }
    
#     for agent in agents:
#         # Get all leads for this agent in Bitcoin Depot this month
#         leads = frappe.get_all(
#             "ATM Leads",
#             filters={
#                 "executive_name": agent["executive_name"],
#                 "company": "Bitcoin Depot",
#                 "post_date": [">=", current_month_start],
#                 "post_date": ["<=", current_month_end]
#             },
#             fields=["name", "workflow_state", "modified"]
#         )
        
#         lead_count = len(leads)
#         if lead_count == 0:
#             continue
        
#         # Initialize agent counts
#         agent_data = {
#             "executive_name": agent["executive_name"],
#             "pseudo_name": agent["pseudo_name"],
#             "lead_generated": lead_count,
#             "approved": 0,
#             "pending_approved": 0,
#             "rejected": 0,
#             "agreement_sent": 0,
#             "agreement_not_signed": 0,
#             "signed": 0,
#             "modified": None
#         }
        
#         # Count statuses
#         for lead in leads:
#             status = lead.workflow_state.lower()
            
#             if "approved" in status:
#                 if "pending" in status:
#                     agent_data["pending_approved"] += 1
#                 else:
#                     agent_data["approved"] += 1
#             elif "rejected" in status:
#                 agent_data["rejected"] += 1
#             elif "agreement sent" in status or "agreement_sent" in status:
#                 agent_data["agreement_sent"] += 1
                
#                 # Check if signed (assuming Signed is a separate status)
#                 if "signed" in status:
#                     agent_data["signed"] += 1
#                 else:
#                     agent_data["agreement_not_signed"] += 1
#             elif "signed" in status:
#                 agent_data["signed"] += 1
            
#             # Track latest modification
#             if not agent_data["modified"] or lead.modified > agent_data["modified"]:
#                 agent_data["modified"] = lead.modified
        
#         # Calculate percentages
#         agent_data["rejection_rate"] = round((agent_data["rejected"] / agent_data["lead_generated"]) * 100, 2) if agent_data["lead_generated"] > 0 else 0
#         agent_data["signed_rate"] = round((agent_data["signed"] / agent_data["lead_generated"]) * 100, 2) if agent_data["lead_generated"] > 0 else 0
        
#         report_data.append(agent_data)
        
#         # Update totals
#         totals["lead_generated"] += agent_data["lead_generated"]
#         totals["approved"] += agent_data["approved"]
#         totals["pending_approved"] += agent_data["pending_approved"]
#         totals["rejected"] += agent_data["rejected"]
#         totals["agreement_sent"] += agent_data["agreement_sent"]
#         totals["agreement_not_signed"] += agent_data["agreement_not_signed"]
#         totals["signed"] += agent_data["signed"]
    
#     # Calculate overall percentages
#     totals["rejection_rate"] = round((totals["rejected"] / totals["lead_generated"]) * 100, 2) if totals["lead_generated"] > 0 else 0
#     totals["signed_rate"] = round((totals["signed"] / totals["lead_generated"]) * 100, 2) if totals["lead_generated"] > 0 else 0
#     totals["agreement_conversion_rate"] = round((totals["signed"] / totals["agreement_sent"]) * 100, 2) if totals["agreement_sent"] > 0 else 0
    
#     return {
#         "report_data": sorted(report_data, key=lambda x: x["modified"] or "", reverse=True),
#         "totals": totals,
#         "month": current_month_start.strftime("%B %Y")
#     }