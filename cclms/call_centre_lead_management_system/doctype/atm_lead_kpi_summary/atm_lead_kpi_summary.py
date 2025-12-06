# Copyright (c) 2025, Galaxy and contributors
# For license information, please see license.txt

import calendar
from datetime import date
from collections import defaultdict

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class ATMLeadKPISummary(Document):
    """
    Monthly KPI master:
    - One document per Year + Month (optionally filtered by Executive).
    - Child rows per (Company, State, State Code, Agent).
    - Counts & average days calculated from ATM Lead State History.
    """

    @frappe.whitelist()
    def rebuild_rows(self):
        """
        Rebuild KPI rows for this Year + Month.

        Uses ATM Lead State History as the source of truth.

        If self.executive_name is set:
            -> Only history for that agent (h.agent or l.executive_name).
        If empty:
            -> All agents.
        """

        # Optional protection: don't overwrite manually adjusted/final summaries
        if getattr(self, "status", None) in ("Adjusted", "Final"):
            frappe.throw(
                "This summary is already Adjusted/Final. "
                "Duplicate it if you need a fresh calculation."
            )

        if not self.year or not self.month:
            frappe.throw("Please set Year and Month before rebuilding KPI rows.")

        year = int(self.year)
        month = int(self.month)

        # 1) Month range
        start_day = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_day = date(year, month, last_day)

        self.from_date = start_day
        self.to_date = end_day

        # Clear existing rows
        self.set("kpi_rows", [])

        # 2) Build SQL conditions for history fetch
        conditions = ["h.change_date BETWEEN %s AND %s"]
        params = [start_day, end_day]

        # Optional filter by executive_name (agent)
        # If you set Executive on the parent, we only show that agent's KPI.
        if getattr(self, "executive_name", None):
            conditions.append(
                "IFNULL(h.agent, IFNULL(l.executive_name, '')) = %s"
            )
            params.append(self.executive_name)

        # Optional filter by branch (if you want)
        if getattr(self, "branch", None):
            conditions.append("l.branch = %s")
            params.append(self.branch)

        where_clause = " AND ".join(conditions)

        # 3) Fetch history rows within month (and optional filters)
        history = frappe.db.sql(
            f"""
            SELECT
                h.parent             AS lead_name,
                h.from_state,
                h.to_state,
                h.change_date,
                h.days_in_state,
                h.agent              AS history_agent,
                l.company,
                l.state,
                l.state_code,
                l.executive_name     AS lead_agent
            FROM `tabATM Lead State History` h
            JOIN `tabATM Leads` l
                ON l.name = h.parent
            WHERE {where_clause}
            """,
            params,
            as_dict=True,
        )

        if not history:
            # Nothing in this month (for this filter)
            self.leads_posted = 0
            self.leads_approved = 0
            self.leads_signed = 0
            self.leads_converted = 0
            self.leads_installed = 0
            self.leads_removed = 0
            self.leads_sign_rejected = 0
            self.avg_approval_days = 0
            self.avg_sign_days = 0
            self.status = "Calculated"
            self.save()
            return

        # -------------------------------
        # Aggregate in buckets
        # Key: (company, state, state_code, agent_name)
        # -------------------------------
        buckets = defaultdict(lambda: {
            "leads_posted": 0,
            "leads_approved": 0,
            "leads_signed": 0,
            "leads_converted": 0,
            "leads_installed": 0,
            "leads_removed": 0,
            "leads_sign_rejected": 0,
            "approval_days_sum": 0.0,
            "approval_days_count": 0,
            "sign_days_sum": 0.0,
            "sign_days_count": 0,
        })

        for h in history:
            company = h.company or "Unknown"
            state = h.state or ""
            state_code = h.state_code or ""
            # Prefer explicit history.agent (Data); fall back to lead.executive_name
            agent_name = h.history_agent or h.lead_agent or "Unknown"

            key = (company, state, state_code, agent_name)
            b = buckets[key]

            from_state = (h.from_state or "").strip()
            to_state = (h.to_state or "").strip()
            days_in_state = h.days_in_state

            # -------- Counts (per bucket) --------

            # Submitted: Draft -> Submitted
            if from_state == "Draft" and to_state == "Submitted":
                b["leads_posted"] += 1

            if to_state == "Approved":
                b["leads_approved"] += 1

            if to_state == "Signed":
                b["leads_signed"] += 1

            if to_state == "Converted":
                b["leads_converted"] += 1

            if to_state == "Installed":
                b["leads_installed"] += 1

            if to_state in ("installed/Removed", "Removed"):
                b["leads_removed"] += 1

            if to_state == "Signed Rejected":
                b["leads_sign_rejected"] += 1

            # -------- Durations (per bucket) --------
            if days_in_state is not None:
                try:
                    d = float(days_in_state)
                except (TypeError, ValueError):
                    d = None

                if d is not None:
                    # Approval cycle: time spent in Submitted
                    if from_state == "Submitted":
                        b["approval_days_sum"] += d
                        b["approval_days_count"] += 1

                    # Sign cycle: time spent in Agreement Sent
                    if from_state == "Agreement Sent":
                        b["sign_days_sum"] += d
                        b["sign_days_count"] += 1

        # -------------------------------
        # Totals for parent
        # -------------------------------
        total_posted = 0
        total_approved = 0
        total_signed = 0
        total_converted = 0
        total_installed = 0
        total_removed = 0
        total_sign_rejected = 0

        total_approval_days_sum = 0.0
        total_approval_days_count = 0
        total_sign_days_sum = 0.0
        total_sign_days_count = 0

        # -------------------------------
        # Materialize child rows + accumulate parent totals
        # -------------------------------
        for (company, state, state_code, agent_name), b in buckets.items():
            row = self.append("kpi_rows", {})
            row.company = company
            row.state = state
            row.state_code = state_code

            # IMPORTANT: set kpi_agent fieldtype = Data in DocType,
            # otherwise you'll hit Link issues for old or missing agents.
            row.kpi_agent = agent_name

            row.leads_posted = b["leads_posted"]
            row.leads_approved = b["leads_approved"]
            row.leads_signed = b["leads_signed"]
            row.leads_converted = b["leads_converted"]
            row.leads_installed = b["leads_installed"]
            row.leads_removed = b["leads_removed"]
            row.leads_sign_rejected = b["leads_sign_rejected"]

            if b["approval_days_count"]:
                row.avg_approval_days = b["approval_days_sum"] / b["approval_days_count"]

            if b["sign_days_count"]:
                row.avg_sign_days = b["sign_days_sum"] / b["sign_days_count"]

            # Accumulate parent totals
            total_posted += b["leads_posted"]
            total_approved += b["leads_approved"]
            total_signed += b["leads_signed"]
            total_converted += b["leads_converted"]
            total_installed += b["leads_installed"]
            total_removed += b["leads_removed"]
            total_sign_rejected += b["leads_sign_rejected"]

            total_approval_days_sum += b["approval_days_sum"]
            total_approval_days_count += b["approval_days_count"]
            total_sign_days_sum += b["sign_days_sum"]
            total_sign_days_count += b["sign_days_count"]

        # -------------------------------
        # Set parent totals / averages
        # -------------------------------
        self.leads_posted = total_posted
        self.leads_approved = total_approved
        self.leads_signed = total_signed
        self.leads_converted = total_converted
        self.leads_installed = total_installed
        self.leads_removed = total_removed
        self.leads_sign_rejected = total_sign_rejected

        if total_approval_days_count:
            self.avg_approval_days = total_approval_days_sum / total_approval_days_count
        else:
            self.avg_approval_days = 0

        if total_sign_days_count:
            self.avg_sign_days = total_sign_days_sum / total_sign_days_count
        else:
            self.avg_sign_days = 0

        self.status = "Calculated"
        self.save()

    @frappe.whitelist()
    def apply_transfers(self):
        """
        Legacy button support.

        You said you don't want transfer-to-closer logic now,
        but the form is still calling apply_transfers.

        To keep UX simple, we just rebuild rows again.
        """
        self.rebuild_rows()

@frappe.whitelist()
def generate_kpi_for_month(year=None, month=None):
    """
    Create / update one ATM Lead KPI Summary per Sales Agent
    for the given month, then rebuild rows for each.

    - If year/month not given -> use current month.
    - Works even if year/month fields are Select (string) in DocType.
    """

    today = getdate()

    # Allow both int and string values coming in
    if year is None:
        year_int = today.year
    else:
        year_int = int(year)

    if month is None:
        month_int = today.month
    else:
        month_int = int(month)

    # Strings as stored in Select fields
    year_str = str(year_int)
    month_str = f"{month_int:02d}"

    # Get all Sales Agents
    agents = frappe.get_all("Sales Agent", fields=["name"])

    for a in agents:
        agent_name = a.name

        # Try to find existing summary for this agent + month (string match)
        summary_name = frappe.db.get_value(
            "ATM Lead KPI Summary",
            {
                "year": year_str,
                "month": month_str,
                "executive_name": agent_name,
            },
            "name",
        )

        if summary_name:
            doc = frappe.get_doc("ATM Lead KPI Summary", summary_name)
        else:
            doc = frappe.new_doc("ATM Lead KPI Summary")
            doc.year = year_str           # Select expects string
            doc.month = month_str         # "01".."12"
            doc.executive_name = agent_name

            # state_filter only to satisfy autoname/link; not used in logic
            doc.state_filter = "Signed"   # or any valid Workflow State
            doc.status = "Draft"
            doc.insert(ignore_permissions=True)

        # Rebuild KPI for this agent & month
        doc.rebuild_rows()

    return f"Generated / updated KPI summaries for {len(agents)} agents for {month_str}-{year_str}"
