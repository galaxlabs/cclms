import frappe
from frappe.utils import getdate


def _get_current_year_month():
    """Return (year:int, month_str:'MM') for today's date."""
    today = getdate()
    return today.year, f"{today.month:02d}"


def _get_target_states():
    """
    Get ALL existing Workflow States from the system.

    This guarantees that any value we put in `state_filter`
    is a valid Workflow State name, so LinkValidationError
    for "Lead Status (Workflow State)" cannot happen.

    If you later want to limit to just ATM states, you can
    filter or hard-code after we confirm this works.
    """
    return frappe.get_all("Workflow State", pluck="name")


@frappe.whitelist()
def update_all_summaries():
    """
    Hourly job:
    - For current year/month
    - For every Sales Agent
    - For every Workflow State that exists
    => get or create ATM Lead KPI Summary
    => run rebuild_rows() if status is Draft or Calculated
    """
    year, month = _get_current_year_month()

    # all sales agents
    executives = frappe.get_all("Sales Agent", pluck="name")
    if not executives:
        return

    states = _get_target_states()
    if not states:
        frappe.logger("atm_kpi").info("ATM KPI: no Workflow States found.")
        return

    for exec_name in executives:
        for state_name in states:
            # find existing summary for (year, month, executive, state)
            name = frappe.db.get_value(
                "ATM Lead KPI Summary",
                {
                    "year": year,
                    "month": month,
                    "executive_name": exec_name,
                    "state_filter": state_name,
                },
            )

            if name:
                doc = frappe.get_doc("ATM Lead KPI Summary", name)
            else:
                # create new summary doc
                doc = frappe.get_doc(
                    {
                        "doctype": "ATM Lead KPI Summary",
                        "year": year,
                        "month": month,
                        "executive_name": exec_name,
                        "state_filter": state_name,
                        "status": "Draft",  # valid option in your Doctype
                    }
                )
                doc.insert(ignore_permissions=True)

            # do not overwrite Adjusted / Final
            if doc.status in ("Adjusted", "Final"):
                continue

            # rebuild KPI rows
            try:
                doc.rebuild_rows()
                frappe.logger("atm_kpi").info(
                    f"KPI Summary {doc.name}: rebuilt {len(doc.kpi_rows)} rows"
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    "ATM Lead KPI Summary: rebuild_rows failed",
                )

    frappe.db.commit()
