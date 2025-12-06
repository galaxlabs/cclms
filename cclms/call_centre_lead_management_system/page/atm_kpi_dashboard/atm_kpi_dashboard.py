import frappe
from frappe.utils import getdate, add_days, get_first_day, get_last_day


def _resolve_period(timespan=None, from_date=None, to_date=None):
    """Same logic as report: This Week / This Month / Custom."""
    today = getdate()
    timespan = (timespan or "This Week").strip()

    if timespan == "This Week":
        weekday = today.weekday()  # Monday=0
        start = add_days(today, -weekday)
        end = add_days(start, 6)
    elif timespan == "This Month":
        start = get_first_day(today)
        end = get_last_day(today)
    elif timespan == "Custom":
        start = getdate(from_date or today)
        end = getdate(to_date or today)
    else:
        # fallback
        start = getdate(from_date or today)
        end = getdate(to_date or today)

    return start, end


@frappe.whitelist()
def get_company_breakdown(timespan=None, from_date=None, to_date=None):
    """
    Group KPI by Company for the same period logic as Weekly ATM KPI.

    Returns:
    {
      "rows": [
        {
          "company": "...",
          "agent_count": 3,
          "created": 10,
          "approved": 7,
          "rejected": 2,
          "signed": 5,
          "converted": 3,
          "installed": 2,
          "sign_rejected": 1
        }, ...
      ],
      "totals": {
        "companies": 4,
        "agent_count": 12,
        "created": ...,
        "approved": ...,
        "rejected": ...,
        "signed": ...,
        "converted": ...,
        "installed": ...,
        "sign_rejected": ...,
        "period": "YYYY-MM-DD → YYYY-MM-DD",
      },
      "companies": ["Company A", "Company B", ...]
    }
    """
    start, end = _resolve_period(timespan, from_date, to_date)

    # --- Base created/posted per company + distinct agents ---
    leads = frappe.db.sql(
        """
        SELECT
            company,
            executive_name
        FROM `tabATM Leads`
        WHERE
            post_date BETWEEN %s AND %s
        """,
        (start, end),
        as_dict=True,
    )

    if not leads:
        return {
            "rows": [],
            "totals": {
                "companies": 0,
                "agent_count": 0,
                "created": 0,
                "approved": 0,
                "rejected": 0,
                "signed": 0,
                "converted": 0,
                "installed": 0,
                "sign_rejected": 0,
                "period": f"{start} → {end}",
            },
            "companies": [],
        }

    company_map = {}

    def _ensure_company(cname):
        cname = cname or "Unknown"
        if cname not in company_map:
            company_map[cname] = {
                "company": cname,
                "created": 0,
                "approved": 0,
                "rejected": 0,
                "signed": 0,
                "converted": 0,
                "installed": 0,
                "sign_rejected": 0,
                "agents": set(),
            }
        return company_map[cname]

    for l in leads:
        cname = l.company or "Unknown"
        rec = _ensure_company(cname)
        rec["created"] += 1
        if l.executive_name:
            rec["agents"].add(l.executive_name)

    # --- Transitions in this period, grouped by company ---
    history = frappe.db.sql(
        """
        SELECT
            l.company,
            h.to_state
        FROM `tabATM Lead State History` h
        JOIN `tabATM Leads` l ON l.name = h.parent
        WHERE
            h.change_date BETWEEN %s AND %s
        """,
        (start, end),
        as_dict=True,
    )

    for h in history:
        cname = h.company or "Unknown"
        rec = _ensure_company(cname)

        to_state = (h.to_state or "").strip()
        if to_state == "Approved":
            rec["approved"] += 1
        if to_state == "Rejected":
            rec["rejected"] += 1
        if to_state == "Signed":
            rec["signed"] += 1
        if to_state == "Converted":
            rec["converted"] += 1
        if to_state == "Installed":
            rec["installed"] += 1
        if to_state == "Signed Rejected":
            rec["sign_rejected"] += 1

    # --- Final rows + totals ---
    rows = []
    totals = {
        "companies": 0,
        "agent_count": 0,
        "created": 0,
        "approved": 0,
        "rejected": 0,
        "signed": 0,
        "converted": 0,
        "installed": 0,
        "sign_rejected": 0,
        "period": f"{start} → {end}",
    }

    for cname, rec in company_map.items():
        rec["agent_count"] = len(rec["agents"])
        totals["companies"] += 1
        totals["agent_count"] += rec["agent_count"]
        totals["created"] += rec["created"]
        totals["approved"] += rec["approved"]
        totals["rejected"] += rec["rejected"]
        totals["signed"] += rec["signed"]
        totals["converted"] += rec["converted"]
        totals["installed"] += rec["installed"]
        totals["sign_rejected"] += rec["sign_rejected"]

        # we don't need to send the internal set
        rec.pop("agents", None)

        rows.append(rec)

    # sort by created desc
    rows.sort(key=lambda r: r.get("created", 0), reverse=True)

    return {
        "rows": rows,
        "totals": totals,
        "companies": [r["company"] for r in rows],
    }
@frappe.whitelist()
def get_signed_matrix(timespan=None, from_date=None, to_date=None):
    """
    Build an Agent × Company matrix for SIGNED leads only.

    Uses the same period logic as the dashboard:
    - timespan: This Week / This Month / Custom
    - from_date, to_date for Custom
    """
    start, end = _resolve_period(timespan, from_date, to_date)

    # All signed leads in this period (by sign_date)
    leads = frappe.db.sql(
        """
        SELECT
            company,
            executive_name,
            executive_name_ps
        FROM `tabATM Leads`
        WHERE
            sign_date IS NOT NULL
            AND sign_date BETWEEN %s AND %s
        """,
        (start, end),
        as_dict=True,
    )

    if not leads:
        return {
            "companies": [],
            "agents": [],
            "totals": {
                "signed_total": 0,
                "per_company": {},
            },
        }

    # ---- Agent map & companies ----
    companies = set()
    agent_map = {}

    def ensure_agent(exec_name, official_name=None):
        key = exec_name or "__UNASSIGNED__"
        if key not in agent_map:
            agent_map[key] = {
                "executive_name": key,
                "official_name": official_name or "",
                "pseudo_name": "",
                "kpi_min": None,
                "kpi_max": None,
                "signed_total": 0,
                "per_company": {},
            }
        return agent_map[key]

    for l in leads:
        comp = l.company or "Unknown"
        companies.add(comp)

        a = ensure_agent(l.executive_name, l.executive_name_ps)
        a["signed_total"] += 1
        a["per_company"][comp] = a["per_company"].get(comp, 0) + 1

    companies = sorted(companies)

    # ensure all agents have keys for all companies
    for a in agent_map.values():
        for c in companies:
            a["per_company"].setdefault(c, 0)

    # ---- Fetch Sales Agent info (pseudo, full name, KPI) ----
    exec_ids = [k for k in agent_map.keys() if k != "__UNASSIGNED__"]
    if exec_ids:
        sales_agents = frappe.db.get_all(
            "Sales Agent",
            filters={"name": ["in", exec_ids]},
            fields=["name", "agent_name", "full_name", "kpi_minimum", "kpi_maximum"],
        )
        sa_map = {x.name: x for x in sales_agents}

        for key, a in agent_map.items():
            if key == "__UNASSIGNED__":
                a["pseudo_name"] = a["pseudo_name"] or "Unassigned"
                a["official_name"] = a["official_name"] or "Unassigned"
                continue

            sa = sa_map.get(key)
            if not sa:
                continue

            a["pseudo_name"] = sa.agent_name or a["pseudo_name"]
            a["official_name"] = sa.full_name or a["official_name"]
            a["kpi_min"] = sa.kpi_minimum
            a["kpi_max"] = sa.kpi_maximum

    # ---- Build rows & totals ----
    rows = list(agent_map.values())
    rows.sort(key=lambda x: x.get("signed_total", 0), reverse=True)

    totals = {
        "signed_total": 0,
        "per_company": {c: 0 for c in companies},
    }

    for a in rows:
        totals["signed_total"] += a["signed_total"]
        for c in companies:
            totals["per_company"][c] += a["per_company"].get(c, 0)

    return {
        "companies": companies,
        "agents": rows,
        "totals": totals,
    }

# import frappe
# from frappe.utils import getdate


# @frappe.whitelist()
# def get_dashboard_data(year=None, month=None):
#     """
#     Return aggregated KPI data for the given month.

#     Output:
#     {
#         "year": 2025,
#         "month": "12",
#         "companies": [...],
#         "agents": [
#             {
#                 "executive_name": "...",
#                 "full_name": "...",
#                 "kpi_min": 0,
#                 "kpi_max": 0,
#                 "per_company": { "Bitcoin Depot": 4, ... },
#                 "signed_total": 6
#             },
#             ...
#         ],
#         "totals": {
#             "per_company": { "Bitcoin Depot": 18, ... },
#             "signed_total": 36
#         }
#     }
#     """

#     today = getdate()
#     year = int(year or today.year)
#     month = int(month or today.month)
#     month_str = f"{month:02d}"

#     rows = frappe.db.sql(
#         """
#         SELECT
#             s.executive_name,
#             COALESCE(sa.full_name, s.executive_name) AS full_name,
#             sa.kpi_minimum,
#             sa.kpi_maximum,
#             r.company,
#             SUM(r.leads_signed) AS signed
#         FROM `tabATM Lead KPI Summary` s
#         JOIN `tabATM Lead KPI Row` r
#             ON r.parent = s.name
#         LEFT JOIN `tabSales Agent` sa
#             ON sa.name = s.executive_name
#         WHERE
#             s.year = %s
#             AND s.month = %s
#         GROUP BY
#             s.executive_name,
#             sa.full_name,
#             sa.kpi_minimum,
#             sa.kpi_maximum,
#             r.company
#         ORDER BY
#             full_name
#         """,
#         (year, month_str),
#         as_dict=True,
#     )

#     if not rows:
#         return {
#             "year": year,
#             "month": month_str,
#             "companies": [],
#             "agents": [],
#             "totals": {"per_company": {}, "signed_total": 0},
#         }

#     companies = sorted({r.company for r in rows if r.company})

#     agents_map = {}
#     totals_per_company = {c: 0 for c in companies}
#     grand_total_signed = 0

#     for r in rows:
#         exec_name = r.executive_name
#         company = r.company
#         signed = r.signed or 0

#         if exec_name not in agents_map:
#             agents_map[exec_name] = {
#                 "executive_name": exec_name,
#                 "full_name": r.full_name,
#                 "kpi_min": r.kpi_minimum or 0,
#                 "kpi_max": r.kpi_maximum or 0,
#                 "per_company": {c: 0 for c in companies},
#                 "signed_total": 0,
#             }

#         agent = agents_map[exec_name]

#         if company:
#             agent["per_company"][company] += signed
#             totals_per_company[company] += signed

#         agent["signed_total"] += signed
#         grand_total_signed += signed

#     agents = list(agents_map.values())

#     agents = [a for a in agents if (a["signed_total"] or 0) > 0]

#     return {
#         "year": year,
#         "month": month_str,
#         "companies": companies,
#         "agents": agents,
#         "totals": {
#             "per_company": totals_per_company,
#             "signed_total": grand_total_signed,
#         },
#     }
