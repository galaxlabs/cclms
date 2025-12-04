# Copyright (c) 2025, Galaxy and contributors
# For license information, please see license.txt

import calendar
from datetime import date
from collections import defaultdict

import frappe
from frappe.model.document import Document


class ATMLeadKPISummary(Document):

    @frappe.whitelist()
    def rebuild_rows(self):
        """
        Build KPI rows for this: executive_name + state_filter + month + year,
        across ALL companies.
        """

        # protect Adjusted/Final from being overwritten
        if self.status in ("Adjusted", "Final"):
            frappe.throw("This summary is already Adjusted/Final. Duplicate it if you need a fresh calculation.")

        if not (self.year and self.month and self.executive_name and self.state_filter):
            frappe.throw("Please set Year, Month, Executive and Lead Status.")

        year = int(self.year)
        month = int(self.month)

        # 1) Month range
        start_day = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_day = date(year, month, last_day)

        self.from_date = start_day
        self.to_date = end_day

        # 2) Clear existing rows
        self.set("kpi_rows", [])

        credit_mode = self.credit_mode or "Generator"

        # Workflow State name (text used in ATM Leads.status)
        workflow_state_name = frappe.db.get_value(
            "Workflow State", self.state_filter, "name"
        ) or self.state_filter

        # 3) Get all ATM Leads in this workflow state for this executive
        #    No docstatus filter, because you use workflow only.
        filters = {
            "status": workflow_state_name,
            "executive_name": self.executive_name,
        }
        if self.branch:
            filters["branch"] = self.branch

        leads = frappe.db.get_all(
            "ATM Leads",
            fields=[
                "name",
                "company",
                "executive_name",
                "executive_name_ps",
                "lead_owner",
                "state",
                "state_code",
                "post_date",
                "approve_date",
                "sign_date",
                "convert_date",
                "install_date",
                "remove_date",
                "sign_rejected",
                "approved_days",
                "sign_days",
                "status",
            ],
            filters=filters,
        )

        # 4) Bucket by (company, state, state_code)
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

        def in_range(d):
            return d and start_day <= d <= end_day

        for l in leads:
            # Reference date: depends on state_filter
            ref_date = get_reference_date_for_lead(l, workflow_state_name)
            if not in_range(ref_date):
                # This lead is in that state, but not in this month
                continue

            # Decide who gets credit logically
            agent_name = resolve_kpi_agent_for_lead(l, credit_mode, self.executive_name)
            if not agent_name:
                continue

            key = (l.company, l.state, l.state_code)
            b = buckets[key]

            # Fill counters based on individual date fields
            if in_range(l.post_date):
                b["leads_posted"] += 1
            if in_range(l.approve_date):
                b["leads_approved"] += 1
            if in_range(l.sign_date):
                b["leads_signed"] += 1
            if in_range(l.convert_date):
                b["leads_converted"] += 1
            if in_range(l.install_date):
                b["leads_installed"] += 1
            if in_range(l.remove_date):
                b["leads_removed"] += 1
            if in_range(l.sign_rejected):
                b["leads_sign_rejected"] += 1

            if l.approved_days:
                b["approval_days_sum"] += float(l.approved_days)
                b["approval_days_count"] += 1
            if l.sign_days:
                b["sign_days_sum"] += float(l.sign_days)
                b["sign_days_count"] += 1

        # 5) Fill child rows
        for (company, state, state_code), b in buckets.items():
            row = self.append("kpi_rows", {})
            row.company = company
            row.state = state
            row.state_code = state_code

            # default credit = parent executive_name (generator)
            row.kpi_agent = self.executive_name

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

        self.status = "Calculated"
        self.save()

    @frappe.whitelist()
    def apply_transfers(self):
        """
        Apply manual closer adjustments:
        - For each row where transfer_checked && transfer_to_agent
          -> move KPI credit to transfer_to_agent.
        - We do NOT touch ATM Leads.
        """
        if self.status not in ("Draft", "Calculated", "Adjusted"):
            frappe.throw("You can only adjust a summary in Draft / Calculated / Adjusted status.")

        changed = False

        for row in self.kpi_rows:
            if row.transfer_checked and row.transfer_to_agent:
                # Move credit to closer
                row.kpi_agent = row.transfer_to_agent
                # Clear the flag once applied
                row.transfer_checked = 0
                changed = True

        if changed:
            self.status = "Adjusted"
            self.save()
            frappe.msgprint("Closer adjustments applied. KPI Agent updated in rows.")
        else:
            frappe.msgprint("No rows marked for closer adjustment.")


# -------------------------
# Helper functions (module level)
# -------------------------

def get_reference_date_for_lead(lead, workflow_state_name):
    """
    Given a lead and a workflow state name, return the relevant date field
    that indicates when the lead entered that state.
    NOTE: make sure workflow_state_name strings match your actual Workflow States.
    """
    state_date_field_map = {
        "Posted": lead.post_date,
        "Approved": lead.approve_date,
        "Signed": lead.sign_date,
        "Converted": lead.convert_date,
        "Installed": lead.install_date,
        "Removed": lead.remove_date,
        "Sign Rejected": lead.sign_rejected,
    }
    # default: use post_date if state not in map
    return state_date_field_map.get(workflow_state_name, lead.post_date)


def resolve_kpi_agent_for_lead(lead, credit_mode, parent_executive):
    """
    Determine the KPI agent for a lead based on credit mode.
    - "Generator" => use lead.executive_name (Sales Agent link)
    - "Owner"     => use lead.executive_name_ps (full name) if set, else executive_name
    - "Both"      => prefer executive_name_ps if set, else executive_name
    If nothing found, fallback to parent_executive.
    """
    if credit_mode == "Generator":
        return lead.executive_name or parent_executive

    if credit_mode == "Owner":
        return lead.executive_name_ps or lead.executive_name or parent_executive

    if credit_mode == "Both":
        return lead.executive_name_ps or lead.executive_name or parent_executive

    return parent_executive
