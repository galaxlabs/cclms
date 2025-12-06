import frappe
from frappe.utils import (
    getdate,
    add_days,
    flt,
    get_first_day,
    get_last_day,
	formatdate,
)


def execute(filters=None):
    filters = filters or {}

    # -----------------------------
    # 1) Resolve TIME SPAN
    # -----------------------------
    today = getdate()
    timespan = (filters.get("timespan") or "This Week").strip()

    if timespan == "This Week":
        # Monday to Sunday of current week
        weekday = today.weekday()  # Monday=0
        from_date = add_days(today, -weekday)
        to_date = add_days(from_date, 6)
    elif timespan == "This Month":
        from_date = get_first_day(today)
        to_date = get_last_day(today)
    elif timespan == "Custom":
        from_date = getdate(filters.get("from_date") or today)
        to_date = getdate(filters.get("to_date") or today)
    else:
        # fallback: treat like Custom
        from_date = getdate(filters.get("from_date") or today)
        to_date = getdate(filters.get("to_date") or today)

    # -----------------------------
    # 2) Leads CREATED in this period (post_date)
    #    -> "Created / Posted"
    # -----------------------------
    leads = frappe.db.sql(
        """
        SELECT
            l.name,
            l.executive_name,
            l.executive_name_ps,          -- Official Name
            sa.agent_name AS pseudo_name, -- Pseudo Name
            l.company,
            l.branch,
            l.state,
            l.state_code
        FROM `tabATM Leads` l
        LEFT JOIN `tabSales Agent` sa
            ON sa.name = l.executive_name
        WHERE
            l.post_date BETWEEN %s AND %s
        """,
        (from_date, to_date),
        as_dict=True,
    )

    if not leads:
        columns = get_columns()
        return columns, [], None, None, [
            {
                "label": "Active Agents (Leads Created)",
                "value": 0,
                "indicator": "Blue",
                "datatype": "Int",
            },
            {
                "label": "Period",
                "value": f"{from_date} → {to_date}",
                "indicator": "Blue",
                "datatype": "Data",
            },
        ]

    # Agents who created at least one lead in this period
    agent_leads = {}
    for l in leads:
        exec_name = l.executive_name or "Unknown"

        # Official Name from ATM Leads.executive_name_ps
        official_name = l.executive_name_ps or exec_name
        # Pseudo Name from Sales Agent.agent_name (fallback to official_name)
        pseudo_name = l.pseudo_name or official_name

        if exec_name not in agent_leads:
            agent_leads[exec_name] = {
                "executive_name": exec_name,
                "official_name": official_name,
                "pseudo_name": pseudo_name,
                # base counts for this period
                "created": 0,          # Created/Posted in this period
                "approved": 0,
                "rejected": 0,
                "signed": 0,
                "converted": 0,
                "installed": 0,
                "sign_rejected": 0,
            }

        agent_leads[exec_name]["created"] += 1

    # -----------------------------
    # 3) State transitions in this period (ATM Lead State History)
    # -----------------------------
    history = frappe.db.sql(
        """
        SELECT
            h.parent         AS lead_name,
            h.from_state,
            h.to_state,
            h.change_date,
            h.days_in_state,
            l.executive_name
        FROM `tabATM Lead State History` h
        JOIN `tabATM Leads` l ON l.name = h.parent
        WHERE
            h.change_date BETWEEN %s AND %s
        """,
        (from_date, to_date),
        as_dict=True,
    )

    for h in history:
        exec_name = h.executive_name or "Unknown"

        # Only count for agents who created leads in this period
        if exec_name not in agent_leads:
            continue

        entry = agent_leads[exec_name]

        to_state = (h.to_state or "").strip()

        # Counts we care about
        if to_state == "Approved":
            entry["approved"] += 1

        if to_state == "Rejected":
            entry["rejected"] += 1

        if to_state == "Signed":
            entry["signed"] += 1

        if to_state == "Converted":
            entry["converted"] += 1

        if to_state == "Installed":
            entry["installed"] += 1

        if to_state == "Signed Rejected":
            entry["sign_rejected"] += 1

    # -----------------------------
    # 4) MONTHLY "Approved vs Created" for each agent
    #    from all created in THIS MONTH (calendar)
    # -----------------------------
    month_start = get_first_day(today)
    month_end = get_last_day(today)

    monthly_created = frappe.db.sql(
        """
        SELECT
            executive_name,
            COUNT(*) AS created_month
        FROM `tabATM Leads`
        WHERE
            post_date BETWEEN %s AND %s
        GROUP BY executive_name
        """,
        (month_start, month_end),
        as_dict=True,
    )
    created_map = {r.executive_name: r.created_month for r in monthly_created}

    monthly_transitions = frappe.db.sql(
        """
        SELECT
            l.executive_name,
            SUM(CASE WHEN h.to_state = 'Approved' THEN 1 ELSE 0 END) AS approved_month
        FROM `tabATM Lead State History` h
        JOIN `tabATM Leads` l ON l.name = h.parent
        WHERE
            h.change_date BETWEEN %s AND %s
        GROUP BY
            l.executive_name
        """,
        (month_start, month_end),
        as_dict=True,
    )
    monthly_map = {m.executive_name: m for m in monthly_transitions}

    # -----------------------------
    # 5) Build final rows + ratios
    # -----------------------------
    data = []
    total_agents = 0

    total_created = 0
    total_approved = 0

    sum_ratio_approved_created = 0.0
    agents_with_ratio_approved_created = 0

    sum_month_ratio_approved_created = 0.0
    agents_with_month_ratio_approved_created = 0

    for exec_name, a in agent_leads.items():
        created = a["created"]
        if created <= 0:
            continue

        approved = a["approved"]
        rejected = a["rejected"]
        signed = a["signed"]
        converted = a["converted"]
        installed = a["installed"]
        sign_rejected = a["sign_rejected"]

        # ---- Period ratios ----
        ratio_approved_created = approved / created if created > 0 else 0.0
        ratio_rejected_created = rejected / created if created > 0 else 0.0
        ratio_signed_approved = signed / approved if approved > 0 else 0.0
        ratio_converted_signed = converted / signed if signed > 0 else 0.0
        ratio_installed_signed = installed / signed if signed > 0 else 0.0
        ratio_sign_rejected_signed = (
            sign_rejected / signed if signed > 0 else 0.0
        )

        sum_ratio_approved_created += ratio_approved_created
        agents_with_ratio_approved_created += 1

        # ---- Monthly Approved vs Created ----
        month_ratio_approved_created = 0.0
        created_month = created_map.get(exec_name, 0) or 0
        mt = monthly_map.get(exec_name)
        approved_month = mt.approved_month if mt else 0

        if created_month > 0:
            month_ratio_approved_created = approved_month / created_month
            sum_month_ratio_approved_created += month_ratio_approved_created
            agents_with_month_ratio_approved_created += 1

        row = {
            "official_name": a["official_name"],
            "pseudo_name": a["pseudo_name"],
            "created": created,
            "approved": approved,
            "rejected": rejected,
            "signed": signed,
            "converted": converted,
            "installed": installed,
            "sign_rejected": sign_rejected,
            # Period ratios (%)
            "ratio_approved_created": ratio_approved_created * 100,
            "ratio_rejected_created": ratio_rejected_created * 100,
            "ratio_signed_approved": ratio_signed_approved * 100,
            "ratio_converted_signed": ratio_converted_signed * 100,
            "ratio_installed_signed": ratio_installed_signed * 100,
            "ratio_sign_rejected_signed": ratio_sign_rejected_signed * 100,
            # Monthly ratio Approved vs Created (%)
            "monthly_ratio_approved_created": month_ratio_approved_created * 100,
        }
        data.append(row)

        total_agents += 1
        total_created += created
        total_approved += approved

    # Sort by created desc
    data.sort(key=lambda d: d.get("created", 0), reverse=True)

    # -----------------------------
    # 6) Chart: Approved vs Created for period
    # -----------------------------
    labels = [d["pseudo_name"] for d in data]
    created_values = [d["created"] for d in data]
    approved_values = [d["approved"] for d in data]

    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "Created", "values": created_values},
                {"name": "Approved", "values": approved_values},
            ],
        },
        "type": "bar",
        "height": 240,
    }

    # -----------------------------
    # 7) Summary cards (no "week" wording)
    # -----------------------------
    avg_ratio_approved_created = 0.0
    if agents_with_ratio_approved_created:
        avg_ratio_approved_created = (
            sum_ratio_approved_created / agents_with_ratio_approved_created
        )

    avg_month_ratio_approved_created = 0.0
    if agents_with_month_ratio_approved_created:
        avg_month_ratio_approved_created = (
            sum_month_ratio_approved_created / agents_with_month_ratio_approved_created
        )

    def ratio_indicator(ratio):
        if ratio >= 0.7:
            return "Green"
        elif ratio >= 0.4:
            return "Orange"
        return "Red"
    period_str = f"{formatdate(from_date, 'dd-MM-yyyy')} → {formatdate(to_date, 'dd-MM-yyyy')}"

    report_summary = [
        {
            "label": "Active Agents (Leads Created)",
            "value": total_agents,
            "indicator": "Blue",
            "datatype": "Int",
        },
        {
            "label": "Total Created",
            "value": total_created,
            "indicator": "Blue",
            "datatype": "Int",
        },
        {
            "label": "Total Approved",
            "value": total_approved,
            "indicator": "Blue",
            "datatype": "Int",
        },
        {
            "label": "Avg Approved vs Created (Period) %",
            "value": flt(avg_ratio_approved_created * 100, 2),
            "indicator": ratio_indicator(avg_ratio_approved_created),
            "datatype": "Percent",
        },
        {
            "label": "Avg Approved vs Created (Month) %",
            "value": flt(avg_month_ratio_approved_created * 100, 2),
            "indicator": ratio_indicator(avg_month_ratio_approved_created),
            "datatype": "Percent",
        },
        {
            "label": "Period",
            "value": period_str,
            "indicator": "Blue",
            "datatype": "Data",
        },
    ]

    columns = get_columns()
    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {
            "label": "Official Name",
            "fieldname": "official_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Pseudo Name",
            "fieldname": "pseudo_name",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": "Created / Posted",
            "fieldname": "created",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": "Approved",
            "fieldname": "approved",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": "Rejected",
            "fieldname": "rejected",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": "Signed",
            "fieldname": "signed",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": "Converted",
            "fieldname": "converted",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": "Installed",
            "fieldname": "installed",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": "Sign Rejected",
            "fieldname": "sign_rejected",
            "fieldtype": "Int",
            "width": 120,
        },
        # Ratios (Period)
        {
            "label": "Approved vs Created (%)",
            "fieldname": "ratio_approved_created",
            "fieldtype": "Percent",
            "width": 170,
        },
        {
            "label": "Rejected vs Created (%)",
            "fieldname": "ratio_rejected_created",
            "fieldtype": "Percent",
            "width": 170,
        },
        {
            "label": "Signed vs Approved (%)",
            "fieldname": "ratio_signed_approved",
            "fieldtype": "Percent",
            "width": 170,
        },
        {
            "label": "Converted vs Signed (%)",
            "fieldname": "ratio_converted_signed",
            "fieldtype": "Percent",
            "width": 180,
        },
        {
            "label": "Installed vs Signed (%)",
            "fieldname": "ratio_installed_signed",
            "fieldtype": "Percent",
            "width": 180,
        },
        {
            "label": "Sign Rejected vs Signed (%)",
            "fieldname": "ratio_sign_rejected_signed",
            "fieldtype": "Percent",
            "width": 200,
        },
        # Monthly (fixed to calendar month)
        {
            "label": "Approved vs Created (Month) (%)",
            "fieldname": "monthly_ratio_approved_created",
            "fieldtype": "Percent",
            "width": 190,
        },
    ]

# import frappe
# from frappe.utils import (
#     getdate,
#     add_days,
#     flt,
#     get_first_day,
#     get_last_day,
# )


# def execute(filters=None):
#     filters = filters or {}

#     # -----------------------------
#     # 1) Resolve WEEK date range
#     # -----------------------------
#     today = getdate()

#     from_date = filters.get("from_date")
#     to_date = filters.get("to_date")

#     if from_date:
#         from_date = getdate(from_date)
#     else:
#         # Monday of current week
#         weekday = today.weekday()  # Monday=0
#         from_date = add_days(today, -weekday)

#     if to_date:
#         to_date = getdate(to_date)
#     else:
#         to_date = today

#     # -----------------------------
#     # 2) Leads CREATED this week (post_date)
#     #    -> "Created / Posted"
#     # -----------------------------
#     leads = frappe.db.sql(
#         """
#         SELECT
#             l.name,
#             l.executive_name,
#             l.executive_name_ps,          -- Official Name
#             sa.agent_name AS pseudo_name, -- Pseudo Name
#             l.company,
#             l.branch,
#             l.state,
#             l.state_code
#         FROM `tabATM Leads` l
#         LEFT JOIN `tabSales Agent` sa
#             ON sa.name = l.executive_name
#         WHERE
#             l.post_date BETWEEN %s AND %s
#         """,
#         (from_date, to_date),
#         as_dict=True,
#     )

#     if not leads:
#         columns = get_columns()
#         return columns, [], None, None, [
#             {
#                 "label": "Active Agents This Week",
#                 "value": 0,
#                 "indicator": "Blue",
#                 "datatype": "Int",
#             }
#         ]

#     # Agents who created at least one lead this week
#     agent_leads = {}
#     for l in leads:
#         exec_name = l.executive_name or "Unknown"

#         # Official Name from ATM Leads.executive_name_ps
#         official_name = l.executive_name_ps or exec_name
#         # Pseudo Name from Sales Agent.agent_name (fallback to official_name)
#         pseudo_name = l.pseudo_name or official_name

#         if exec_name not in agent_leads:
#             agent_leads[exec_name] = {
#                 "executive_name": exec_name,
#                 "official_name": official_name,
#                 "pseudo_name": pseudo_name,
#                 # weekly base counts
#                 "created": 0,          # Created/Posted in this week
#                 "approved": 0,
#                 "rejected": 0,
#                 "signed": 0,
#                 "converted": 0,
#                 "installed": 0,
#                 "sign_rejected": 0,
#                 # monthly ratio placeholder
#                 "monthly_ratio_approved_created": 0.0,
#             }

#         agent_leads[exec_name]["created"] += 1

#     # -----------------------------
#     # 3) WEEK state transitions (ATM Lead State History)
#     # -----------------------------
#     history = frappe.db.sql(
#         """
#         SELECT
#             h.parent         AS lead_name,
#             h.from_state,
#             h.to_state,
#             h.change_date,
#             h.days_in_state,
#             l.executive_name
#         FROM `tabATM Lead State History` h
#         JOIN `tabATM Leads` l ON l.name = h.parent
#         WHERE
#             h.change_date BETWEEN %s AND %s
#         """,
#         (from_date, to_date),
#         as_dict=True,
#     )

#     for h in history:
#         exec_name = h.executive_name or "Unknown"

#         # Only count for agents who created leads this week
#         if exec_name not in agent_leads:
#             continue

#         entry = agent_leads[exec_name]

#         from_state = (h.from_state or "").strip()
#         to_state = (h.to_state or "").strip()

#         # --- Weekly counts we care about ---
#         if to_state == "Approved":
#             entry["approved"] += 1

#         if to_state == "Rejected":
#             entry["rejected"] += 1

#         if to_state == "Signed":
#             entry["signed"] += 1

#         if to_state == "Converted":
#             entry["converted"] += 1

#         if to_state == "Installed":
#             entry["installed"] += 1

#         if to_state == "Signed Rejected":
#             entry["sign_rejected"] += 1

#         # (Pending state exists but we ignore it in metrics, as requested)

#     # -----------------------------
#     # 4) MONTHLY "Approved vs Created" for each agent
#     #    "avreg from all created in this month"
#     # -----------------------------
#     month_start = get_first_day(to_date)
#     month_end = get_last_day(to_date)

#     # monthly created per executive
#     monthly_created = frappe.db.sql(
#         """
#         SELECT
#             executive_name,
#             COUNT(*) AS created_month
#         FROM `tabATM Leads`
#         WHERE
#             post_date BETWEEN %s AND %s
#         GROUP BY executive_name
#         """,
#         (month_start, month_end),
#         as_dict=True,
#     )
#     created_map = {
#         r.executive_name: r.created_month for r in monthly_created
#     }

#     # monthly approvals + rejects per executive
#     monthly_transitions = frappe.db.sql(
#         """
#         SELECT
#             l.executive_name,
#             SUM(CASE WHEN h.to_state = 'Approved' THEN 1 ELSE 0 END) AS approved_month,
#             SUM(CASE WHEN h.to_state = 'Rejected' THEN 1 ELSE 0 END) AS rejected_month
#         FROM `tabATM Lead State History` h
#         JOIN `tabATM Leads` l ON l.name = h.parent
#         WHERE
#             h.change_date BETWEEN %s AND %s
#         GROUP BY
#             l.executive_name
#         """,
#         (month_start, month_end),
#         as_dict=True,
#     )
#     monthly_map = {m.executive_name: m for m in monthly_transitions}

#     # -----------------------------
#     # 5) Build final rows + WEEK ratios + MONTH ratio
#     # -----------------------------
#     data = []
#     total_agents = 0

#     total_created = 0
#     total_approved = 0

#     sum_week_ratio_approved_created = 0.0
#     agents_with_week_approved_created = 0

#     sum_month_ratio_approved_created = 0.0
#     agents_with_month_approved_created = 0

#     for exec_name, a in agent_leads.items():
#         created = a["created"]
#         if created <= 0:
#             continue

#         approved = a["approved"]
#         rejected = a["rejected"]
#         signed = a["signed"]
#         converted = a["converted"]
#         installed = a["installed"]
#         sign_rejected = a["sign_rejected"]

#         # ---- WEEK ratios ----
#         ratio_approved_created = (
#             approved / created if created > 0 else 0.0
#         )
#         ratio_rejected_created = (
#             rejected / created if created > 0 else 0.0
#         )
#         ratio_signed_approved = (
#             signed / approved if approved > 0 else 0.0
#         )
#         ratio_converted_signed = (
#             converted / signed if signed > 0 else 0.0
#         )
#         ratio_installed_signed = (
#             installed / signed if signed > 0 else 0.0
#         )
#         ratio_sign_rejected_signed = (
#             sign_rejected / signed if signed > 0 else 0.0
#         )

#         # accumulate for average approved/created (week)
#         sum_week_ratio_approved_created += ratio_approved_created
#         agents_with_week_approved_created += 1

#         # ---- MONTHLY Approved vs Created ----
#         month_ratio_approved_created = 0.0
#         created_month = created_map.get(exec_name, 0) or 0
#         mt = monthly_map.get(exec_name)
#         approved_month = 0
#         if mt:
#             approved_month = mt.approved_month or 0

#         if created_month > 0:
#             month_ratio_approved_created = approved_month / created_month
#             sum_month_ratio_approved_created += month_ratio_approved_created
#             agents_with_month_approved_created += 1

#         row = {
#             "official_name": a["official_name"],
#             "pseudo_name": a["pseudo_name"],
#             "created": created,
#             "approved": approved,
#             "rejected": rejected,
#             "signed": signed,
#             "converted": converted,
#             "installed": installed,
#             "sign_rejected": sign_rejected,
#             # WEEK ratios (%)
#             "ratio_approved_created": ratio_approved_created * 100,
#             "ratio_rejected_created": ratio_rejected_created * 100,
#             "ratio_signed_approved": ratio_signed_approved * 100,
#             "ratio_converted_signed": ratio_converted_signed * 100,
#             "ratio_installed_signed": ratio_installed_signed * 100,
#             "ratio_sign_rejected_signed": ratio_sign_rejected_signed * 100,
#             # MONTH ratio Approved vs Created (%)
#             "monthly_ratio_approved_created": month_ratio_approved_created * 100,
#         }
#         data.append(row)

#         total_agents += 1
#         total_created += created
#         total_approved += approved

#     # Sort by created desc
#     data.sort(key=lambda d: d.get("created", 0), reverse=True)

#     # -----------------------------
#     # 6) Chart data (simple: Approved vs Created (Week))
#     # -----------------------------
#     labels = [d["pseudo_name"] for d in data]
#     created_values = [d["created"] for d in data]
#     approved_values = [d["approved"] for d in data]

#     chart = {
#         "data": {
#             "labels": labels,
#             "datasets": [
#                 {"name": "Created (Week)", "values": created_values},
#                 {"name": "Approved (Week)", "values": approved_values},
#             ],
#         },
#         "type": "bar",
#         "height": 240,
#     }

#     # -----------------------------
#     # 7) Summary cards
#     # -----------------------------
#     avg_week_ratio_approved_created = 0.0
#     if agents_with_week_approved_created:
#         avg_week_ratio_approved_created = (
#             sum_week_ratio_approved_created / agents_with_week_approved_created
#         )

#     avg_month_ratio_approved_created = 0.0
#     if agents_with_month_approved_created:
#         avg_month_ratio_approved_created = (
#             sum_month_ratio_approved_created / agents_with_month_approved_created
#         )

#     def ratio_indicator(ratio):
#         if ratio >= 0.7:
#             return "Green"
#         elif ratio >= 0.4:
#             return "Orange"
#         return "Red"

#     report_summary = [
#         {
#             "label": "Active Agents (Leads Created This Week)",
#             "value": total_agents,
#             "indicator": "Blue",
#             "datatype": "Int",
#         },
#         {
#             "label": "Total Created (Week)",
#             "value": total_created,
#             "indicator": "Blue",
#             "datatype": "Int",
#         },
#         {
#             "label": "Total Approved (Week)",
#             "value": total_approved,
#             "indicator": "Blue",
#             "datatype": "Int",
#         },
#         {
#             "label": "Avg Approved vs Created (Week) %",
#             "value": flt(avg_week_ratio_approved_created * 100, 2),
#             "indicator": ratio_indicator(avg_week_ratio_approved_created),
#             "datatype": "Percent",
#         },
#         {
#             "label": "Avg Approved vs Created (Month) %",
#             "value": flt(avg_month_ratio_approved_created * 100, 2),
#             "indicator": ratio_indicator(avg_month_ratio_approved_created),
#             "datatype": "Percent",
#         },
#     ]

#     columns = get_columns()
#     return columns, data, None, chart, report_summary


# def get_columns():
#     return [
#         {
#             "label": "Official Name",
#             "fieldname": "official_name",
#             "fieldtype": "Data",
#             "width": 200,
#         },
#         {
#             "label": "Pseudo Name",
#             "fieldname": "pseudo_name",
#             "fieldtype": "Data",
#             "width": 160,
#         },
#         {
#             "label": "Created / Posted (Week)",
#             "fieldname": "created",
#             "fieldtype": "Int",
#             "width": 140,
#         },
#         {
#             "label": "Approved (Week)",
#             "fieldname": "approved",
#             "fieldtype": "Int",
#             "width": 120,
#         },
#         {
#             "label": "Rejected (Week)",
#             "fieldname": "rejected",
#             "fieldtype": "Int",
#             "width": 120,
#         },
#         {
#             "label": "Signed (Week)",
#             "fieldname": "signed",
#             "fieldtype": "Int",
#             "width": 120,
#         },
#         {
#             "label": "Converted (Week)",
#             "fieldname": "converted",
#             "fieldtype": "Int",
#             "width": 120,
#         },
#         {
#             "label": "Installed (Week)",
#             "fieldname": "installed",
#             "fieldtype": "Int",
#             "width": 120,
#         },
#         {
#             "label": "Sign Rejected (Week)",
#             "fieldname": "sign_rejected",
#             "fieldtype": "Int",
#             "width": 130,
#         },
#         # Ratios
#         {
#             "label": "Approved vs Created (Week) %",
#             "fieldname": "ratio_approved_created",
#             "fieldtype": "Percent",
#             "width": 170,
#         },
#         {
#             "label": "Rejected vs Created (Week) %",
#             "fieldname": "ratio_rejected_created",
#             "fieldtype": "Percent",
#             "width": 170,
#         },
#         {
#             "label": "Signed vs Approved (Week) %",
#             "fieldname": "ratio_signed_approved",
#             "fieldtype": "Percent",
#             "width": 170,
#         },
#         {
#             "label": "Converted vs Signed (Week) %",
#             "fieldname": "ratio_converted_signed",
#             "fieldtype": "Percent",
#             "width": 180,
#         },
#         {
#             "label": "Installed vs Signed (Week) %",
#             "fieldname": "ratio_installed_signed",
#             "fieldtype": "Percent",
#             "width": 180,
#         },
#         {
#             "label": "Sign Rejected vs Signed (Week) %",
#             "fieldname": "ratio_sign_rejected_signed",
#             "fieldtype": "Percent",
#             "width": 200,
#         },
#         {
#             "label": "Approved vs Created (Month) %",
#             "fieldname": "monthly_ratio_approved_created",
#             "fieldtype": "Percent",
#             "width": 190,
#         },
#     ]
