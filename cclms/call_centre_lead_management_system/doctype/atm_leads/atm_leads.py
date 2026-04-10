# Copyright (c) 2024, Galaxy and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, nowdate, getdate


US_PHONE_FIELDS = ("business_phone_number", "personal_cell_phone")

# ---------------------------------------------------------------------------
# Duplicate-location detection constants
# ---------------------------------------------------------------------------
# States where a location is considered "committed" – new leads ARE allowed
# even when an existing lead for the same company+location is in these states.
DEDUP_ALLOWED_STATES = frozenset(["Signed", "Installed"])

# Pre-built SQL literal for IN clauses (safe – only our own constants)
_EXEMPT_SQL = ", ".join(f"'{s}'" for s in sorted(DEDUP_ALLOWED_STATES))

# Window in days: within this period, a duplicate blocks creation.
# After this period, the stale (non-Signed/Installed) lead is auto-deleted.
DEDUP_WINDOW_DAYS = 15

# lat/lng match tolerance: ~11 metres (0.0001 decimal degrees)
_LAT_LNG_TOL = 0.0001

# Address-related fields monitored for change on updates
_LOC_FIELDS = ("address", "zip_code", "full_address", "latitude", "longitude", "city")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _normalize_phone_value(value):
    if value in (None, ""):
        return value

    raw = str(value).strip()
    if not raw:
        return ""

    raw = re.sub(r"\s+", " ", raw)
    digits = re.sub(r"\D", "", raw)

    # Standardize common US numbers while preserving older/international values.
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"{digits[0]}-{digits[1:4]}-{digits[4:7]}-{digits[7:]}"

    return raw


def _norm(value):
    """Normalise a string for dedup comparison: lowercase, strip, collapse spaces."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _build_location_sql(doc_or_ns):
    """
    Build a SQL fragment (sql_str, params_dict) that matches rows by location
    using OR of whichever fields (full_address / address+zip / lat+lng) are set.
    Works with both Document objects and plain namespaces/dicts.
    Returns (None, {}) when no usable location fields are found.
    """
    def _get(field):
        if isinstance(doc_or_ns, dict):
            return doc_or_ns.get(field)
        return getattr(doc_or_ns, field, None)

    parts = []
    params = {}

    fa = _norm(_get("full_address"))
    if fa:
        parts.append("LOWER(TRIM(full_address)) = %(loc_fa)s")
        params["loc_fa"] = fa

    addr = _norm(_get("address"))
    zc   = _norm(_get("zip_code"))
    if addr and zc:
        parts.append(
            "(LOWER(TRIM(address)) = %(loc_addr)s AND LOWER(TRIM(zip_code)) = %(loc_zc)s)"
        )
        params["loc_addr"] = addr
        params["loc_zc"]   = zc

    try:
        lat = float(_get("latitude") or 0)
        lng = float(_get("longitude") or 0)
    except (TypeError, ValueError):
        lat = lng = 0.0
    if lat and lng:
        parts.append(
            "(latitude  BETWEEN %(loc_lat_lo)s AND %(loc_lat_hi)s"
            " AND longitude BETWEEN %(loc_lng_lo)s AND %(loc_lng_hi)s)"
        )
        params.update({
            "loc_lat_lo": lat - _LAT_LNG_TOL,
            "loc_lat_hi": lat + _LAT_LNG_TOL,
            "loc_lng_lo": lng - _LAT_LNG_TOL,
            "loc_lng_hi": lng + _LAT_LNG_TOL,
        })

    if not parts:
        return None, {}
    return f"({' OR '.join(parts)})", params


class ATMLeads(Document):
    """
    ATM Leads DocType controller.

    Responsibilities:
    - Duplicate location detection (before_insert and on address change).
    - Business validation (company, state restrictions, etc.)
    - Workflow state history tracking (child table + Agent Stage Ledger).
    - Phone field normalisation.
    """

    # -----------------------------------------------------------------------
    # Frappe document hooks
    # -----------------------------------------------------------------------

    def before_insert(self):
        """
        Runs before the very first DB insert – blocks even Draft creation
        when a duplicate location already exists in an active pipeline state.
        """
        self.check_duplicate_location()

    def validate(self):
        self.normalize_phone_fields()
        self.validate_lead_state()
        # On updates, re-run dedup only when an address field was actually changed
        if not self.is_new():
            self._recheck_dedup_on_address_change()

    def before_save(self):
        self.log_workflow_change()

    # -----------------------------------------------------------------------
    # Duplicate-location detection
    # -----------------------------------------------------------------------

    def _recheck_dedup_on_address_change(self):
        """Re-check dedup on save only when at least one location field changed."""
        old = self.get_doc_before_save() or frappe._dict()
        changed = any(
            _norm(getattr(old, f, "")) != _norm(getattr(self, f, ""))
            for f in _LOC_FIELDS
        )
        if changed:
            self.check_duplicate_location()

    def check_duplicate_location(self):
        """
        Two-tier location dedup.

        Tier 1 – CROSS-COMPANY, no age window:
            If ANY lead at this location is in Signed or Installed state
            (regardless of which company owns it) → block permanently.
            No one, from any company, may create a new lead at a committed location.

        Tier 2 – SAME-COMPANY only, 15-day window:
            If the SAME company already has a non-committed lead at this location:
              age < 15 days → block with countdown.
              age ≥ 15 days → auto-delete stale lead, allow creation.
            Other companies are NOT affected by Tier 2.

        Skip entirely when THIS document is already Signed/Installed (no re-check on edit).
        Administrator always bypasses.
        """
        if frappe.session.user == "Administrator":
            return

        # If this lead itself is already committed, don't re-validate on edits
        current_state = self.workflow_state or "Draft"
        if current_state in DEDUP_ALLOWED_STATES:
            return

        self_name = self.name or "__new__"

        # Build the location predicate (OR of whichever fields are populated)
        loc_sql, loc_params = _build_location_sql(self)
        if not loc_sql:
            return  # no location data to compare

        from frappe.utils import date_diff, nowdate

        today = getdate(nowdate())

        # ── Tier 1: Cross-company Signed/Installed check ─────────────────────
        tier1 = frappe.db.sql(
            f"""
            SELECT name, workflow_state, company, post_date, creation
            FROM `tabATM Leads`
            WHERE name != %(sn)s
              AND docstatus < 2
              AND workflow_state IN ({_EXEMPT_SQL})
              AND {loc_sql}
            ORDER BY creation ASC
            LIMIT 1
            """,
            {"sn": self_name, **loc_params},
            as_dict=True,
        )
        if tier1:
            dup = tier1[0]
            lead_link = frappe.utils.get_link_to_form("ATM Leads", dup["name"])
            state_label = dup.get("workflow_state") or "Signed/Installed"
            company_label = dup.get("company") or _("Unknown Company")
            frappe.throw(
                _(
                    "<b>Location Permanently Locked</b><br><br>"
                    "A committed ATM deal already exists at this location:<br>"
                    "Lead: {0} &nbsp;|&nbsp; State: <b>{1}</b> &nbsp;|&nbsp; Company: <b>{2}</b><br><br>"
                    "Once a location reaches <b>Signed</b> or <b>Installed</b> status, "
                    "no new lead can be created at that location by <b>any company</b>."
                ).format(lead_link, state_label, company_label),
                title=_("Duplicate Location – Committed Deal"),
            )

        # ── Tier 2: Same-company windowed check (non-committed states) ────────
        if not self.company:
            return

        tier2 = frappe.db.sql(
            f"""
            SELECT name, workflow_state, company, post_date, creation
            FROM `tabATM Leads`
            WHERE name != %(sn)s
              AND docstatus < 2
              AND IFNULL(company, '') = %(company)s
              AND (workflow_state IS NULL OR workflow_state NOT IN ({_EXEMPT_SQL}))
              AND {loc_sql}
            ORDER BY creation ASC
            """,
            {"sn": self_name, "company": self.company, **loc_params},
            as_dict=True,
        )
        if not tier2:
            return

        blocked = []   # age < 15 d → block with countdown
        purged   = []  # age ≥ 15 d → auto-delete, then allow

        for dup in tier2:
            ref_date = getdate(dup.get("post_date") or dup.get("creation"))
            age_days = date_diff(today, ref_date)
            if age_days < DEDUP_WINDOW_DAYS:
                blocked.append((dup, age_days))
            else:
                purged.append(dup)

        # Purge stale leads so they don't block creation
        for dup in purged:
            try:
                frappe.delete_doc("ATM Leads", dup["name"], ignore_permissions=True, force=True)
                frappe.logger("atm_dedup").info(
                    f"[ATMLeads.dedup] Purged stale lead {dup['name']} "
                    f"(state={dup['workflow_state']}, age≥{DEDUP_WINDOW_DAYS}d, "
                    f"company={self.company})"
                )
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"ATM Dedup: failed to purge {dup['name']}")

        if blocked:
            dup, age_days = blocked[0]
            remaining = DEDUP_WINDOW_DAYS - age_days
            lead_link = frappe.utils.get_link_to_form("ATM Leads", dup["name"])
            state_label = dup.get("workflow_state") or "Draft"
            frappe.throw(
                _(
                    "<b>Location Locked – {0}-Day Window</b><br><br>"
                    "Your company already has an active lead at this location:<br>"
                    "Lead: {1} &nbsp;|&nbsp; State: <b>{2}</b> &nbsp;|&nbsp; "
                    "Created: <b>{3} day(s) ago</b><br><br>"
                    "Lock expires in <b>{4} more day(s)</b> (window: {5} days).<br>"
                    "Update the existing lead or wait for the window to expire."
                ).format(
                    DEDUP_WINDOW_DAYS,
                    lead_link,
                    state_label,
                    age_days,
                    remaining,
                    DEDUP_WINDOW_DAYS,
                ),
                title=_("Duplicate Location – Within {0}-Day Window").format(DEDUP_WINDOW_DAYS),
            )

    # -----------------------------------------------------------------------
    # Business validation
    # -----------------------------------------------------------------------

    def normalize_phone_fields(self):
        for fieldname in US_PHONE_FIELDS:
            self.set(fieldname, _normalize_phone_value(self.get(fieldname)))

    def validate_lead_state(self):
        """Validate company, required fields, and permitted state restrictions."""

        if not self.company:
            frappe.throw(
                _("Please select a company before saving the lead."),
                title=_("Company Not Selected"),
            )

        if not self.address:
            frappe.throw(
                _("Please enter a valid address."),
                title=_("Address Required"),
            )

        company = frappe.get_doc("Operator Companies", self.company)
        if not company:
            frappe.throw(
                _("The selected company does not exist."),
                title=_("Invalid Company"),
            )

        permitted_states = company.get("permitted_states")
        if permitted_states:
            if not any(s.state_code == self.state_code for s in permitted_states):
                frappe.throw(
                    _("The selected state ({0}) is not allowed for the company {1}.")
                    .format(self.state_code, self.company),
                    title=_("State Not Allowed"),
                )
        else:
            frappe.msgprint(
                _("No restricted states specified for this company. All states are allowed."),
                alert=True,
            )

    # -----------------------------------------------------------------------
    # Workflow state history tracking
    # -----------------------------------------------------------------------

    def log_workflow_change(self):
        """
        On every workflow_state change:
          1. Append a row to the state_history child table.
          2. Insert an immutable row in Agent Stage Ledger.

        Rules:
        - Ignores initial Draft creation (None → Draft).
        - Updates days_in_state on the previous child-table row.
        """

        old_doc = self.get_doc_before_save() or frappe._dict()

        old_state = getattr(old_doc, "workflow_state", None)
        new_state = self.workflow_state

        # If workflow_state not set or unchanged, nothing to record
        if not new_state or old_state == new_state:
            return

        # Ignore initial creation if it's just setting Draft
        if old_state is None and new_state == "Draft":
            return

        today = nowdate()
        today_date = getdate(today)

        # Do we already have history rows?
        prev_row = self.state_history[-1] if self.state_history else None
        first_change = prev_row is None

        # Determine start date for previous state's duration
        if prev_row and prev_row.change_date:
            start_date = getdate(prev_row.change_date)
        else:
            # First tracked transition: assume we were in Draft from post_date
            start_date = getdate(self.post_date) if self.post_date else today_date

        days_in_prev_state = (today_date - start_date).days

        # Update duration on previous child-table row
        if prev_row:
            prev_row.days_in_state = days_in_prev_state

        from_state = "Draft" if first_change else (old_state or "Draft")

        # --- 1. Child table row ---
        row = self.append("state_history", {})
        row.from_state = from_state
        row.to_state = new_state
        row.change_datetime = now_datetime()
        row.change_date = today
        row.changed_by = frappe.session.user or "Administrator"
        row.agent_name = self.executive_name or ""
        row.days_in_state = 0  # updated on the NEXT transition

        # --- 2. Immutable Agent Stage Ledger entry ---
        self._write_stage_ledger(from_state, new_state, days_in_prev_state)

        # --- 3. Auto-create Signs record on first Signed transition ---
        if new_state == "Signed" and not self.mark_signed:
            self._create_signs_record()

        frappe.logger("atm_state_history").info(
            f"[ATMLeads] {self.name}: {from_state} -> {new_state}, "
            f"prev_days={days_in_prev_state}"
        )

    def _write_stage_ledger(self, from_state: str, to_state: str, days_in_prev: int):
        """
        Insert one immutable row in Agent Stage Ledger.
        Silently skips if the DocType is not yet installed (pre-migration).
        Never raises – a ledger failure must never block a workflow transition.
        """
        try:
            if not frappe.db.exists("DocType", "Agent Stage Ledger"):
                return
            frappe.get_doc({
                "doctype": "Agent Stage Ledger",
                "lead": self.name,
                "employee": self.executive_name or "",
                "company": self.company or "",
                "branch": self.branch or "",
                "state_code": self.state_code or "",
                "from_state": from_state,
                "to_state": to_state,
                "stage_datetime": now_datetime(),
                "stage_date": nowdate(),
                "days_in_prev_state": days_in_prev,
                "changed_by": frappe.session.user or "Administrator",
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Agent Stage Ledger: insert failed")

    def _create_signs_record(self):
        """
        Auto-create a Signs record when this ATM Lead transitions to 'Signed'.

        - Snapshots all key lead data into the Signs document.
        - Sets employee = current executive_name (the lead's agent at sign time).
        - Leaves closing_agent blank — manager fills this in later to assign commission.
        - Sets mark_signed = 1 and signed_record = <Signs name> on this document.
        - Idempotent: skips if mark_signed is already 1 or a Signs record already exists.
        - Never raises — a failure here must not block the workflow transition.
        """
        try:
            if not frappe.db.exists("DocType", "Signs"):
                return

            # Safety: check DB as well in case of concurrent saves
            existing = frappe.db.get_value("Signs", {"atm_leads": self.name}, "name")
            if existing:
                self.mark_signed = 1
                self.signed_record = existing
                return

            signs_doc = frappe.get_doc({
                "doctype": "Signs",
                "_auto_created_by_system": True,
                "atm_leads": self.name,
                "sign_date": self.sign_date or nowdate(),
                "employee": self.executive_name or "",
                # Lead details snapshot
                "company": self.company or "",
                "branch": self.branch or "",
                "state_code": self.state_code or "",
                "business_name": getattr(self, "business_name", "") or "",
                "business_type": getattr(self, "business_type", "") or "",
                "city": getattr(self, "city", "") or "",
                "state": getattr(self, "state", "") or "",
                "address": getattr(self, "full_address", "") or getattr(self, "address", "") or "",
                # closing_agent is intentionally blank — manager assigns later
            })
            signs_doc.insert(ignore_permissions=True)

            # Update this document's indicator fields (they'll be saved with this save)
            self.mark_signed = 1
            self.signed_record = signs_doc.name

            frappe.logger("atm_signs").info(
                f"[ATMLeads] Auto-created Signs {signs_doc.name} for lead {self.name}"
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "ATM Leads: _create_signs_record failed")

    # -------------------------------
    # Simple backfill for a single lead (fallback)
    # -------------------------------

    def sync_state_history_once(self):
        """
        Ensure this lead has a reasonable state history when Version is not available.

        Behavior:
        - If history is empty:
            -> Create one row: Draft -> current workflow_state
               with change_date = post_date or today.
        - If history exists but last.to_state != current workflow_state:
            -> Append row: last.to_state -> current workflow_state
               and update last.days_in_state.
        - If already in sync:
            -> Do nothing.

        Returns:
            True if document was changed and should be saved, else False.
        """

        today = nowdate()
        today_date = getdate(today)

        current_state = self.workflow_state or "Draft"

        # CASE 1: No history at all
        if not self.state_history:
            # Decide the change_date: use post_date if available, else today
            if self.post_date:
                change_date = getdate(self.post_date)
            else:
                change_date = today_date

            row = self.append("state_history", {})
            row.from_state = "Draft"
            row.to_state = current_state
            row.change_datetime = now_datetime()
            row.change_date = change_date
            row.changed_by = frappe.session.user or "Administrator"
            row.agent_name = self.executive_name or ""

            # Days in Draft from post_date to change_date
            if self.post_date:
                row.days_in_state = (change_date - getdate(self.post_date)).days
            else:
                row.days_in_state = 0

            frappe.logger("atm_state_history").info(
                f"[ATMLeads.sync_state_history_once] Seeded history for {self.name}: Draft -> {current_state}"
            )

            return True  # document changed

        # CASE 2: History exists, check if last state matches current workflow_state
        last_row = self.state_history[-1]
        last_state = last_row.to_state or "Draft"

        # Already in sync
        if last_state == current_state:
            return False

        # Need to add a transition from last_state -> current_state
        if last_row.change_date:
            start_date = getdate(last_row.change_date)
        else:
            start_date = getdate(self.post_date) if self.post_date else today_date

        days_in_prev = (today_date - start_date).days
        last_row.days_in_state = days_in_prev

        new_row = self.append("state_history", {})
        new_row.from_state = last_state
        new_row.to_state = current_state
        new_row.change_datetime = now_datetime()
        new_row.change_date = today
        new_row.changed_by = frappe.session.user or "Administrator"
        new_row.agent_name = self.executive_name or ""
        new_row.days_in_state = 0

        frappe.logger("atm_state_history").info(
            f"[ATMLeads.sync_state_history_once] Appended transition for {self.name}: {last_state} -> {current_state}"
        )

        return True  # document changed

    # -------------------------------
    # Rebuild full state history from Version
    # -------------------------------

    def rebuild_state_history_from_versions(self):
        """
        Rebuild the entire state_history table for this lead,
        based on Version records where workflow_state changed.

        - Clears existing state_history.
        - Looks at all Version entries for this doc.
        - For each workflow_state change, appends a row.
        - Calculates days_in_state as days spent in from_state
          (from previous change or post_date).
        """

        # Clear any existing rows
        self.set("state_history", [])

        # Get all Version records for this lead
        versions = frappe.get_all(
            "Version",
            filters={
                "ref_doctype": "ATM Leads",
                "docname": self.name,
            },
            fields=["name", "owner", "creation", "data"],
            order_by="creation asc",
        )
        transitions = []

        for v in versions:
            if not v.get("data"):
                continue

            # data is JSON like: {"changed": [["workflow_state", "Old", "New"], ...], ...}
            try:
                data = frappe.parse_json(v["data"])
            except Exception:
                continue

            changed = data.get("changed") or []
            for change in changed:
                # change is [fieldname, old_value, new_value]
                if len(change) >= 3 and change[0] == "workflow_state":
                    old_state = change[1] or "Draft"
                    new_state = change[2] or old_state
                    transitions.append(
                        {
                            "from_state": old_state,
                            "to_state": new_state,
                            "change_datetime": v["creation"],
                            "change_date": getdate(v["creation"]),
                            "changed_by": v["owner"],
                        }
                    )

        # If no transitions found from Version, fall back to simple single-row logic
        if not transitions:
            return self.sync_state_history_once()

        # Now build rows with days_in_state
        # First state's "from_state" duration is from post_date to its change_date
        prev_change_date = None

        for idx, t in enumerate(transitions):
            cd = t["change_date"]

            if idx == 0:
                # First transition: Draft -> first_state, days in Draft
                if self.post_date:
                    start_date = getdate(self.post_date)
                else:
                    start_date = cd
            else:
                # Duration from previous change to this change
                start_date = prev_change_date or cd

            days_in = (cd - start_date).days

            row = self.append("state_history", {})
            row.from_state = t["from_state"]
            row.to_state = t["to_state"]
            row.change_datetime = t["change_datetime"]
            row.change_date = cd
            row.changed_by = t["changed_by"]
            row.agent_name = self.executive_name or ""
            row.days_in_state = days_in

            prev_change_date = cd

        frappe.logger("atm_state_history").info(
            f"[ATMLeads.rebuild_state_history_from_versions] {self.name}: "
            f"{len(transitions)} transitions rebuilt from Version"
        )

        return True


# -------------------------------
# Global backfill / scheduler entry
# -------------------------------

@frappe.whitelist()
def sync_recent_lead_state_history(from_date=None, limit=1000):
    """
    Rebuild full state history from Version for ATM Leads from a given date onwards.

    Intended usage:
    - Daily scheduler at 5am PKT, processing up to `limit` leads.
    - Only leads with post_date >= from_date are included.

    Args:
        from_date (str | None): "YYYY-MM-DD", default "2025-08-10"
        limit (int): max number of leads to process in one run (default 1000)

    Returns:
        dict: {"processed": N, "changed": M, "failed": F, "errors": [...]}
    """

    if not from_date:
        from_date = "2025-08-10"

    filters = {
        "docstatus": ["<", 2],
        "post_date": [">=", from_date],
    }

    leads = frappe.get_all(
        "ATM Leads",
        filters=filters,
        fields=["name"],
        order_by="post_date asc, name asc",
        limit=limit,
    )

    processed = 0
    changed_docs = 0
    failed = 0
    errors = []

    for l in leads:
        doc = frappe.get_doc("ATM Leads", l.name)

        try:
            # Rebuild from Version; if no Version found, it falls back to sync_state_history_once()
            if hasattr(doc, "rebuild_state_history_from_versions"):
                changed = doc.rebuild_state_history_from_versions()
            else:
                changed = False

            if changed:
                # Ignore validation/mandatory for backfill only
                doc.flags.ignore_validate = True
                doc.flags.ignore_mandatory = True
                doc.save(ignore_permissions=True)
                changed_docs += 1

        except Exception as e:
            failed += 1
            # Capture full traceback so bench execute can show it
            errors.append({
                "lead": doc.name,
                "error": str(e),
                "traceback": frappe.get_traceback()
            })
            frappe.logger("atm_state_history").error(
                f"[sync_recent_lead_state_history] Failed for {doc.name}: {e}"
            )

        processed += 1

    frappe.db.commit()

    result = {
        "from_date": from_date,
        "processed": processed,
        "changed": changed_docs,
        "failed": failed,
        "errors": errors,
    }

    frappe.logger("atm_state_history").info(
        f"[sync_recent_lead_state_history] {result}"
    )

    return result

# import frappe
# from frappe import _
# from frappe.model.document import Document
# from frappe.utils import now_datetime, nowdate, getdate


# class ATMLeads(Document):

#     def validate(self):
#         # keep your business rules
#         self.validate_lead_state()

#     def before_save(self):
#         # log workflow changes & durations
#         self.log_status_change()

#     def validate_lead_state(self):
#         # -------------------------------
#         # Basic Required Fields
#         # -------------------------------
#         if not self.company:
#             frappe.throw(_("Please select a company before saving the lead."), title=_("Company Not Selected"))

#         if not self.address:
#             frappe.throw(_("Please enter a valid address."), title=_("Address Required"))

#         # -------------------------------
#         # Validate Company Exists
#         # -------------------------------
#         company = frappe.get_doc("Operator Companies", self.company)
#         if not company:
#             frappe.throw(_("The selected company does not exist."), title=_("Invalid Company"))

#         # -------------------------------
#         # State Restriction Check
#         # -------------------------------
#         permitted_states = company.get("permitted_states")
#         if permitted_states:
#             if not any(state.state_code == self.state_code for state in permitted_states):
#                 frappe.throw(
#                     _("The selected state ({0}) is not allowed for the company {1}.")
#                     .format(self.state_code, self.company),
#                     title=_("State Not Allowed"),
#                 )
#         else:
#             frappe.msgprint(
#                 _("No restricted states specified for this company. All states are allowed."),
#                 alert=True,
#             )

#         # duplicate check intentionally disabled here
#         return

#     # -------------------------------
#     # State history + duration
#     # -------------------------------

#     def log_status_change(self):
#         """
#         Append a row in state_history whenever `status` changes.

#         Also update `days_in_state` for the *previous* state based on:
#         - previous change_date (from last history row), or
#         - post_date, if this is the first transition.
#         """

#         old = self.get_doc_before_save() or frappe._dict()
#         old_status = getattr(old, "status", None)
#         new_status = self.status

#         # No change or no new status -> nothing to log
#         if not new_status or old_status == new_status:
#             return

#         today = nowdate()

#         # Find last history row (if any)
#         prev_row = self.state_history[-1] if self.state_history else None

#         # Starting date for previous state's duration:
#         # - If we have a previous row, start from its change_date
#         # - If not, start from lead.post_date
#         if prev_row and prev_row.change_date:
#             start_date = getdate(prev_row.change_date)
#         else:
#             start_date = getdate(self.post_date) if self.post_date else getdate(today)

#         # Duration in days until today
#         days_in_prev_state = (getdate(today) - start_date).days

#         # Store duration on the previous row (duration of its "to_state")
#         if prev_row:
#             prev_row.days_in_state = days_in_prev_state

#         # Now append new history row for this transition
#         row = self.append("state_history", {})
#         row.from_state = old_status or "None"
#         row.to_state = new_status
#         row.change_datetime = now_datetime()
#         row.change_date = today
#         row.changed_by = frappe.session.user
#         row.agent = self.executive_name
#         row.post_date = self.post_date
#         # New state hasn't finished yet, so 0 for now.
#         row.days_in_state = 0
#         row.lead_name = self.name



# import frappe
# import datetime
# from frappe import _
# from frappe.utils import date_diff, nowdate
# from frappe.model.document import Document
# from datetime import timedelta
# import requests

# #from frappe.utils import today, add_days

# class ATMLeads(Document):

#     def validate(self):
#         self.validate_lead_state()

#     def validate_lead_state(self):
#         # -------------------------------
#         # Basic Required Fields
#         # -------------------------------
#         if not self.company:
#             frappe.throw(_("Please select a company before saving the lead."), title=_("Company Not Selected"))

#         if not self.address:
#             frappe.throw(_("Please enter a valid address."), title=_("Address Required"))

#         # -------------------------------
#         # Validate Company Exists
#         # -------------------------------
#         company = frappe.get_doc('Operator Companies', self.company)
#         if not company:
#             frappe.throw(_("The selected company does not exist."), title=_("Invalid Company"))

#         # -------------------------------
#         # State Restriction Check
#         # -------------------------------
#         permitted_states = company.get("permitted_states")
#         if permitted_states:
#             if not any(state.state_code == self.state_code for state in permitted_states):
#                 frappe.throw(
#                     _("The selected state ({0}) is not allowed for the company {1}.")
#                     .format(self.state_code, self.company),
#                     title=_("State Not Allowed")
#                 )
#         else:
#             frappe.msgprint(_("No restricted states specified for this company. All states are allowed."), alert=True)

#         # -------------------------------
#         # Duplicate Check (Disabled)
#         # -------------------------------
#         # frappe.msgprint(_("⚠️ Duplicate validation temporarily disabled."), alert=True)
#         return

# class ATMLeads(Document):

#     def validate(self):
#         self.validate_lead_state()

#     # def before_save(self):
#     #   self.validate_lead_state()

#     def validate_lead_state(self):
#         if not self.company:
#             frappe.throw(_("Please select a company before saving the lead."), title=_("Company Not Selected"))

#         if not self.address:
#             frappe.throw(_("Please enter a valid address."), title=_("Address Required"))

#         # Validate company exists
#         company = frappe.get_doc('Operator Companies', self.company)
#         if not company:
#             frappe.throw(_("The selected company does not exist."), title=_("Invalid Company"))

#         # Check state permission from company
#         permitted_states = company.get("permitted_states")
#         if permitted_states:
#             state_permitted = any(state.state_code == self.state_code for state in permitted_states)
#             if not state_permitted:
#                 frappe.throw (
#                     _("The selected state ({0}) is not allowed for the company {1}.").format(self.state_code, self.company),
#                     title=_("State Not Allowed")
#                 )
#         else:
#             frappe.msgprint(_("No restricted states specified for this company. All states are allowed."), alert=True)

#         # duplication validation process based on three phases
#         # 1. firstly validation should be based on "Installed"
#         # 2. secondly validation should be based on "Signed" status
#         # 3. thirdly validateion should be on other status

#         # 1. check lead existance for validation based on address(location) only for any company.
#         installed_exist = frappe.db.exists("ATM Leads", {
#             "address": self.address,
#             "state": self.state,
#             "state_code": self.state_code,
#             "zip_code": self.zip_code,
#             "city": self.city,
#             "country": self.country,
#             "workflow_state": "Installed",
#             "name": ("!=", self.name)
#         })

#         if installed_exist:
#             # find all leads with other status and try to remove them
#             documents_to_delete = frappe.get_list("ATM Leads", 
#                 filters = {
#                     "address": self.address,
#                     "state": self.state,
#                     "state_code": self.state_code,
#                     "zip_code": self.zip_code,
#                     "city": self.city,
#                     "country": self.country,
#                     "workflow_state": ["in", ["Rejected", "Approved", "Pending", "Draft"]],
#                     "name": ("!=", self.name)
#                 }
#             )

#             for doc in documents_to_delete:
#                 frappe.delete_doc("ATM Leads", doc.name)

#             frappe.db.commit()
            
#             frappe.throw(
#                 _("❗ A lead already exists for the same address in a 'Installed' Lead."),
#                 title=_("Duplicate location")
#             )

#         # 2. check lead existance for validation based on address(location) and company.
#         signed_exist = frappe.db.exists("ATM Leads", {
#             "address": self.address,
#             "company": self.company,
#             "state": self.state,
#             "state_code": self.state_code,
#             "zip_code": self.zip_code,
#             "city": self.city,
#             "country": self.country,
#             "workflow_state": "Signed",
#             "name": ("!=", self.name)
#         })

#         if signed_exist:
#             # find all leads with other status and try to remove them
#             documents_to_delete = frappe.get_list("ATM Leads", 
#                 filters = {
#                     "address": self.address,
#                     "company": self.company,
#                     "state": self.state,
#                     "state_code": self.state_code,
#                     "zip_code": self.zip_code,
#                     "city": self.city,
#                     "country": self.country,
#                     "workflow_state": ["in", ["Rejected", "Re Approval", "Agreement Sent", "Approved", "Pending", "Draft"]],
#                     "name": ("!=", self.name)
#                 }
#             )

#             for doc in documents_to_delete:
#                 frappe.delete_doc("ATM Leads", doc.name)

#             frappe.db.commit()
            
#             frappe.throw(
#                 _("❗ A lead already exists for the same address in a 'Signed' Lead."),
#                 title=_("Duplicate location")
#             )
       
#         # 3. check lead existance for validation, based on address(location) and company with other status.
#         other_status_exist = frappe.db.exists("ATM Leads", {
#             "address": self.address,
#             "company": self.company,
#             "state": self.state,
#             "state_code": self.state_code,
#             "zip_code": self.zip_code,
#             "city": self.city,
#             "country": self.country,
#             "workflow_state": ["in", ["Rejected", "Re Approval", "Agreement Sent", "Approved", "Pending", "Draft"]],
#             "name": ("!=", self.name)
#         })

#         if other_status_exist:
            
#             frappe.throw(
#                 _("❗ A lead already exists for the same address in another status."),
#                 title=_("Duplicate location")
#             )


@frappe.whitelist()
def validate(doc, method):
    if not doc.latitude or not doc.longitude:
        if doc.full_address:
            # Geocode using Google Maps API
            try:
                from urllib.parse import urlencode
                api_key = frappe.db.get_single_value("Google Maps Settings", "api_key")  # Store API key in Settings Doctype
                base_url = "https://maps.googleapis.com/maps/api/geocode/json?"
                params = urlencode({'address': doc.full_address, 'key': api_key})
                url = base_url + params
                response = requests.get(url)
                data = response.json()

                if data['status'] == 'OK':
                    location = data['results'][0]['geometry']['location']
                    doc.latitude = location['lat']
                    doc.longitude = location['lng']
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), "ATM Leads Geocode Error")


# ---------------------------------------------------------------------------
# Client-side pre-save dedup check (returns JSON, does NOT throw)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def check_location_conflict(
    full_address=None,
    address=None,
    zip_code=None,
    latitude=None,
    longitude=None,
    company=None,
    lead_name=None,
):
    """
    Pre-save duplicate-location check for the client-side dialog.

    Returns a dict describing the conflict, or None when there is no conflict.

    Return schema:
        {
            "type":           "permanent" | "windowed",
            "lead":           <name>,
            "state":          <workflow_state>,
            "company":        <company>,
            "age_days":       int | None,      # None for permanent
            "remaining_days": int | None,      # None for permanent
            "window":         DEDUP_WINDOW_DAYS,
        }
    """
    self_name = lead_name or "__new__"

    loc_data = {
        "full_address": full_address,
        "address":      address,
        "zip_code":     zip_code,
        "latitude":     latitude,
        "longitude":    longitude,
    }
    loc_sql, loc_params = _build_location_sql(loc_data)
    if not loc_sql:
        return None

    # ── Tier 1: Cross-company Signed/Installed ────────────────────────────
    tier1 = frappe.db.sql(
        f"""
        SELECT name, workflow_state, company, post_date, creation
        FROM `tabATM Leads`
        WHERE name != %(sn)s
          AND docstatus < 2
          AND workflow_state IN ({_EXEMPT_SQL})
          AND {loc_sql}
        ORDER BY creation ASC
        LIMIT 1
        """,
        {"sn": self_name, **loc_params},
        as_dict=True,
    )
    if tier1:
        dup = tier1[0]
        return {
            "type":           "permanent",
            "lead":           dup["name"],
            "state":          dup.get("workflow_state") or "Signed/Installed",
            "company":        dup.get("company") or "",
            "age_days":       None,
            "remaining_days": None,
            "window":         DEDUP_WINDOW_DAYS,
        }

    # ── Tier 2: Same-company windowed (non-committed) ─────────────────────
    if not company:
        return None

    tier2 = frappe.db.sql(
        f"""
        SELECT name, workflow_state, company, post_date, creation
        FROM `tabATM Leads`
        WHERE name != %(sn)s
          AND docstatus < 2
          AND IFNULL(company, '') = %(company)s
          AND (workflow_state IS NULL OR workflow_state NOT IN ({_EXEMPT_SQL}))
          AND {loc_sql}
        ORDER BY creation ASC
        """,
        {"sn": self_name, "company": company, **loc_params},
        as_dict=True,
    )
    if not tier2:
        return None

    from frappe.utils import date_diff, nowdate, getdate as _getdate
    today = _getdate(nowdate())

    for dup in tier2:
        ref_date = _getdate(dup.get("post_date") or dup.get("creation"))
        age_days  = date_diff(today, ref_date)
        if age_days < DEDUP_WINDOW_DAYS:
            return {
                "type":           "windowed",
                "lead":           dup["name"],
                "state":          dup.get("workflow_state") or "Draft",
                "company":        dup.get("company") or company,
                "age_days":       age_days,
                "remaining_days": DEDUP_WINDOW_DAYS - age_days,
                "window":         DEDUP_WINDOW_DAYS,
            }

    # All candidates are stale – they will be purged on actual save
    return None


# ---------------------------------------------------------------------------
# Company availability check for "Duplicate for Companies" dialog
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_company_availability_for_location(
    lead_name,
    full_address=None,
    address=None,
    zip_code=None,
    latitude=None,
    longitude=None,
    source_company=None,
):
    """
    For the "Duplicate for Companies" button: returns every Operator Company
    with its availability status at this physical location.

    Status values:
        "source"    – this is the lead's own company (cannot duplicate to itself)
        "committed" – ANY company has Signed/Installed at this location (blocks all)
        "locked"    – this company already has a non-committed lead within 15-day window
        "available" – no duplicate exists, safe to create

    Return list item schema:
        {
            "name":          <company docname>,
            "operator_name": <display name>,
            "status":        "source" | "committed" | "locked" | "available",
            "lead":          <lead name> | null,
            "lead_state":    <workflow_state> | null,
            "age_days":      int | null,
            "remaining_days": int | null,
        }
    """
    from frappe.utils import date_diff, nowdate, getdate as _getdate

    loc_data = {
        "full_address": full_address,
        "address":      address,
        "zip_code":     zip_code,
        "latitude":     latitude,
        "longitude":    longitude,
    }
    loc_sql, loc_params = _build_location_sql(loc_data)

    today = _getdate(nowdate())

    # ── Step 1: Is there a cross-company committed lead? (blocks everyone) ──
    committed_lead = None
    if loc_sql:
        tier1 = frappe.db.sql(
            f"""
            SELECT name, workflow_state, company, post_date, creation
            FROM `tabATM Leads`
            WHERE name != %(sn)s
              AND docstatus < 2
              AND workflow_state IN ({_EXEMPT_SQL})
              AND {loc_sql}
            ORDER BY creation ASC
            LIMIT 1
            """,
            {"sn": lead_name or "__new__", **loc_params},
            as_dict=True,
        )
        if tier1:
            committed_lead = tier1[0]

    # ── Step 2: Per-company non-committed leads (same-company window check) ─
    per_company_leads: dict = {}   # company_name -> row
    if loc_sql and not committed_lead:
        rows = frappe.db.sql(
            f"""
            SELECT name, workflow_state, company, post_date, creation
            FROM `tabATM Leads`
            WHERE name != %(sn)s
              AND docstatus < 2
              AND (workflow_state IS NULL OR workflow_state NOT IN ({_EXEMPT_SQL}))
              AND {loc_sql}
            ORDER BY creation ASC
            """,
            {"sn": lead_name or "__new__", **loc_params},
            as_dict=True,
        )
        for row in rows:
            co = row.get("company") or ""
            if co not in per_company_leads:
                per_company_leads[co] = row

    # ── Step 3: Fetch all Operator Companies ─────────────────────────────────
    all_companies = frappe.db.sql(
        "SELECT name, operator_name FROM `tabOperator Companies` ORDER BY operator_name",
        as_dict=True,
    )

    result = []
    for co in all_companies:
        co_name      = co["name"]
        op_name      = co.get("operator_name") or co_name
        entry = {
            "name":           co_name,
            "operator_name":  op_name,
            "status":         "available",
            "lead":           None,
            "lead_state":     None,
            "age_days":       None,
            "remaining_days": None,
        }

        # Source company
        if source_company and co_name == source_company:
            entry["status"] = "source"
            result.append(entry)
            continue

        # Cross-company committed block → status = "committed" for ALL
        if committed_lead:
            entry["status"]     = "committed"
            entry["lead"]       = committed_lead["name"]
            entry["lead_state"] = committed_lead.get("workflow_state") or "Signed/Installed"
            result.append(entry)
            continue

        # Same-company windowed check
        if co_name in per_company_leads:
            dup = per_company_leads[co_name]
            ref_date  = _getdate(dup.get("post_date") or dup.get("creation"))
            age_days  = date_diff(today, ref_date)
            if age_days < DEDUP_WINDOW_DAYS:
                entry["status"]         = "locked"
                entry["lead"]           = dup["name"]
                entry["lead_state"]     = dup.get("workflow_state") or "Draft"
                entry["age_days"]       = age_days
                entry["remaining_days"] = DEDUP_WINDOW_DAYS - age_days
            # else: stale lead → will be purged on actual save → available

        result.append(entry)

    return result
