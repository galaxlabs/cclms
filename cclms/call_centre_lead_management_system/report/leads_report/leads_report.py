import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    return columns, data

def get_columns():
    return [
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Operator Companies", "width": 120},
        {"label": _("Lead"), "fieldname": "lead_name", "fieldtype": "Link", "options": "Leads", "width": 200},
        {"label": _("Lead Owner"), "fieldname": "lead_owner", "fieldtype": "Link", "options": "User", "width": 120},
        {"label": _("Location"), "fieldname": "location", "fieldtype": "Data", "width": 100},
        {"label": _("Executive Name"), "fieldname": "executive_name", "fieldtype": "Link", "options": "Employee", "width": 150},
        {"label": _("Post Date"), "fieldname": "post_date", "fieldtype": "Date", "width": 100},
        {"label": _("Owner Name"), "fieldname": "owner_name", "fieldtype": "Data", "width": 150},
        {"label": _("Business Name"), "fieldname": "business_name", "fieldtype": "Data", "width": 150},
        {"label": _("Status By Company"), "fieldname": "status_by_company", "fieldtype": "Link", "options": "Company Status", "width": 150},
        {"label": _("Action Date"), "fieldname": "action_date", "fieldtype": "Date", "width": 100},
        {"label": _("Country"), "fieldname": "country", "fieldtype": "Link", "options": "Country", "width": 100},
        {"label": _("Business Type"), "fieldname": "business_type", "fieldtype": "Data", "width": 150},
        {"label": _("Value"), "fieldname": "value", "fieldtype": "Currency", "width": 120},
        {"label": _("Total Approved"), "fieldname": "total_approved", "fieldtype": "Int", "width": 120},
        {"label": _("Total Rejected"), "fieldname": "total_rejected", "fieldtype": "Int", "width": 120},
        {"label": _("Total Pending"), "fieldname": "total_pending", "fieldtype": "Int", "width": 120},
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    query = f"""
        SELECT
            l.name as lead_name,
            l.lead_owner,
            l.location,
            l.executive_name,
            l.post_date,
            l.owner_name,
            l.business_name,
            o.status_by_company,
            o.company,
            o.action_date,
            l.country,
            l.business_type,
            l.base_rent AS value,
            SUM(CASE WHEN o.status_by_company = 'Approved' THEN 1 ELSE 0 END) as total_approved,
            SUM(CASE WHEN o.status_by_company = 'Rejected' THEN 1 ELSE 0 END) as total_rejected,
            SUM(CASE WHEN o.status_by_company = 'Review Pending' THEN 1 ELSE 0 END) as total_pending
        FROM
            `tabLeads` l
        LEFT JOIN
            `tabOperator` o ON o.parent = l.name
        WHERE
            {conditions}
        GROUP BY
            l.name, o.company
        ORDER BY
            l.creation DESC
    """
    
    data = frappe.db.sql(query, filters, as_dict=True)
    return data

def get_conditions(filters):
    conditions = []
    if filters.get("lead_owner"):
        conditions.append("l.lead_owner = %(lead_owner)s")
    if filters.get("company"):
        conditions.append("o.company = %(company)s")
    if filters.get("status_by_company"):
        conditions.append("o.status_by_company = %(status_by_company)s")
    if filters.get('location'):
        conditions.append("l.location = %(location)s")
    if filters.get('executive_name'):
        conditions.append("l.executive_name = %(executive_name)s")
    if filters.get('post_date'):
        conditions.append("l.post_date = %(post_date)s")
    if filters.get('country'):
        conditions.append("l.country = %(country)s")
    if filters.get('business_type'):
        conditions.append("l.business_type = %(business_type)s")
    
    return " AND ".join(conditions) if conditions else "1=1"

# import frappe
# from frappe import _

# def execute(filters=None):
#     columns = [
#         _("Company") + ":Link/Leads:200",
#         _("Lead") + ":Link/Leads:200",
#         _("Status") + "::150",
#         _("Owner") + "::120",
#         _("Country") + "::120",
#         _("Business Type") + "::150",
#         _("Value") + ":Currency:120"
#     ]

#     conditions = get_conditions(filters)
#     data = frappe.db.sql("""
#         SELECT 
#             op.company, 
#             leads.name, 
#             op.status_by_company, 
#             leads.owner_name, 
#             leads.country, 
#             leads.business_type,
#             leads.base_rent
#         FROM 
#             `tabLeads` leads, 
#             `tabOperator` op
#         WHERE 
#             leads.name = op.parent 
#             {conditions}
#         ORDER BY 
#             op.company, op.status_by_company
#     """.format(conditions=conditions), filters, as_dict=1)

#     return columns, data

# def get_conditions(filters):
#     conditions = []
#     if filters.get("company"):
#         conditions.append("op.company = %(company)s")
#     if filters.get("status"):
#         conditions.append("op.status_by_company = %(status)s")
#     if filters.get("country"):
#         conditions.append("leads.country = %(country)s")
#     if filters.get("business_type"):
#         conditions.append("leads.business_type = %(business_type)s")
#     return " AND ".join(conditions) if conditions else ""


# # import frappe
# # from frappe import _

# # def execute(filters=None):
# #     columns, data = [], []
    
# #     # Define the columns
# #     columns = [
# #         {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Operator Companies", "width": 120},
# #         {"label": _("Approved"), "fieldname": "approved_count", "fieldtype": "Int", "width": 100},
# #         {"label": _("Rejected"), "fieldname": "rejected_count", "fieldtype": "Int", "width": 100},
# #         {"label": _("Review Pending"), "fieldname": "review_pending_count", "fieldtype": "Int", "width": 120},
# #         {"label": _("Installed"), "fieldname": "installed_count", "fieldtype": "Int", "width": 100},
# #         {"label": _("Signed"), "fieldname": "signed_count", "fieldtype": "Int", "width": 100},
# #     ]
    
# #     # Fetch data
# #     company_statuses = frappe.db.sql("""
# #         SELECT
# #             operator.company AS company,
# #             COUNT(CASE WHEN operator.status_by_company = 'Approved' THEN 1 END) AS approved_count,
# #             COUNT(CASE WHEN operator.status_by_company = 'Rejected' THEN 1 END) AS rejected_count,
# #             COUNT(CASE WHEN operator.status_by_company = 'Review Pending' THEN 1 END) AS review_pending_count,
# #             COUNT(CASE WHEN operator.status_by_company = 'Installed' THEN 1 END) AS installed_count,
# #             COUNT(CASE WHEN operator.status_by_company = 'Signed' THEN 1 END) AS signed_count
# #         FROM
# #             `tabLeads` leads
# #         LEFT JOIN
# #             `tabOperator` operator ON operator.parent = leads.name
# #         GROUP BY
# #             operator.company
# #     """, as_dict=True)
    
# #     data = company_statuses
    
# #     return columns, data

# # import frappe
# # from frappe import _

# # def execute(filters=None):
# #     columns, data = [], []

# #     columns = [
# #         {"label": _("Lead Name"), "fieldname": "lead_name", "fieldtype": "Link", "options": "Lead", "width": 150},
# #         {"label": _("Operator"), "fieldname": "operator", "fieldtype": "Link", "options": "Operator", "width": 150},
# #         {"label": _("Total Approved"), "fieldname": "total_approved", "fieldtype": "Int", "width": 120},
# #         {"label": _("Total Rejected"), "fieldname": "total_rejected", "fieldtype": "Int", "width": 120},
# #         {"label": _("Total Pending"), "fieldname": "total_pending", "fieldtype": "Int", "width": 120},
# #     ]

# #     data = frappe.db.sql("""
# #         SELECT
# #             lead.name as lead_name,
# #             operator.name as operator,
# #             SUM(CASE WHEN operator.status_by_company = 'Approved' THEN 1 ELSE 0 END) as total_approved,
# #             SUM(CASE WHEN operator.status_by_company = 'Rejected' THEN 1 ELSE 0 END) as total_rejected,
# #             SUM(CASE WHEN operator.status_by_company = 'Pending' THEN 1 ELSE 0 END) as total_pending
# #         FROM
# #             `tabLeads` lead
# #         LEFT JOIN
# #             `tabOperator` operator ON operator.parent = lead.name
# #         GROUP BY
# #             lead.name, operator.name
# #     """, as_dict=True)

# #     return columns, data

# # import frappe
# # from frappe.utils import flt, cint, getdate

# # def execute(filters=None):
# #     columns, data = [], []

# #     columns = get_columns()
# #     data = get_data(filters)

# #     return columns, data

# # def get_columns():
# #     return [
# #         {"label": "Lead ID", "fieldname": "lead_id", "fieldtype": "Link", "options": "Leads", "width": 120},
# #         {"label": "Lead Owner", "fieldname": "lead_owner", "fieldtype": "Link", "options": "User", "width": 120},
# #         {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Operator Companies", "width": 150},
# #         {"label": "Action Date", "fieldname": "action_date", "fieldtype": "Date", "width": 100},
# #         {"label": "Status by Company", "fieldname": "status_by_company", "fieldtype": "Data", "width": 150},
# #         {"label": "Business Name", "fieldname": "business_name", "fieldtype": "Data", "width": 200},
# #         {"label": "City", "fieldname": "city", "fieldtype": "Data", "width": 100},
# #         {"label": "Country", "fieldname": "country", "fieldtype": "Link", "options": "Country", "width": 100},
# #     ]

# # def get_data(filters):
# #     conditions = get_conditions(filters)
    
# #     query = """
# #         SELECT
# #             l.name as lead_id, 
# #             l.lead_owner, 
# #             o.company, 
# #             o.action_date, 
# #             o.status_by_company,
# #             l.business_name,
# #             l.city,
# #             l.country
# #         FROM
# #             `tabLeads` l
# #         LEFT JOIN
# #             `tabOperator` o ON o.parent = l.name
# #         WHERE
# #             l.docstatus < 2
# #             {conditions}
# #         ORDER BY
# #             l.creation DESC
# #     """.format(conditions=conditions)

# #     data = frappe.db.sql(query, filters, as_dict=True)
# #     return data

# # def get_conditions(filters):
# #     conditions = []
# #     if filters.get("lead_owner"):
# #         conditions.append("l.lead_owner = %(lead_owner)s")
# #     if filters.get("company"):
# #         conditions.append("o.company = %(company)s")
# #     if filters.get("status_by_company"):
# #         conditions.append("o.status_by_company = %(status_by_company)s")
    
# #     return " AND ".join(conditions) if conditions else ""


# # import frappe
# # from frappe import _

# # def execute(filters=None):
# #     columns = [
# #         {"fieldname": "lead_name", "label": _("Lead Name"), "fieldtype": "Data", "width": 150},
# #         {"fieldname": "lead_owner", "label": _("Lead Owner"), "fieldtype": "Link", "options": "User", "width": 150},
# #         {"fieldname": "location", "label": _("Location"), "fieldtype": "Data", "width": 100},
# #         {"fieldname": "executive_name", "label": _("Executive Name"), "fieldtype": "Link", "options": "Employee", "width": 150},
# #         {"fieldname": "post_date", "label": _("Post Date"), "fieldtype": "Date", "width": 100},
# #         {"fieldname": "owner_name", "label": _("Owner Name"), "fieldtype": "Data", "width": 150},
# #         {"fieldname": "business_name", "label": _("Business Name"), "fieldtype": "Data", "width": 150},
# #         {"fieldname": "status_by_company", "label": _("Status By Company"), "fieldtype": "Link", "options": "Company Status", "width": 150},
# #         {"fieldname": "company", "label": _("Company"), "fieldtype": "Link", "options": "Operator Companies", "width": 150},
# #         {"fieldname": "action_date", "label": _("Action Date"), "fieldtype": "Date", "width": 100},
# #     ]

# #     conditions = []
# #     if filters.get('location'):
# #         conditions.append(f"l.location = '{filters['location']}'")

# #     if filters.get('lead_owner'):
# #         conditions.append(f"l.lead_owner = '{filters['lead_owner']}'")

# #     if filters.get('executive_name'):
# #         conditions.append(f"l.executive_name = '{filters['executive_name']}'")

# #     if filters.get('post_date'):
# #         conditions.append(f"l.post_date = '{filters['post_date']}'")

# #     condition_string = " AND ".join(conditions) if conditions else "1=1"
    
# #     # Join Leads and Operator based on the lead name
# #     query = f"""
# #         SELECT 
# #             l.name AS lead_name,
# #             l.lead_owner,
# #             l.location,
# #             l.executive_name,
# #             l.post_date,
# #             l.owner_name,
# #             l.business_name,
# #             o.status_by_company,
# #             o.company,
# #             o.action_date
# #         FROM `tabLeads` l
# #         LEFT JOIN `tabOperator` o
# #         ON l.name = o.lead_name
# #         WHERE {condition_string}
# #         ORDER BY l.creation DESC
# #     """
    
# #     data = frappe.db.sql(query, as_dict=True)

# #     return columns, data
