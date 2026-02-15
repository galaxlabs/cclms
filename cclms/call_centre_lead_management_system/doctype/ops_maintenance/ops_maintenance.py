# Copyright (c) 2026, Galaxy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class OpsMaintenance(Document):

    def _log(self, title, res):
        self.last_run_log = f"{title}\n{frappe.as_json(res, indent=2)}"
        self.save(ignore_permissions=True)

    @frappe.whitelist()
    def rebuild_deals_since_cutoff(self):
        if not self.cutoff_date:
            frappe.throw("Please set Cutoff Date first.")

        from cclms.services.mirror.fresh_rebuild_operator_deals import run
        res = run(
            cutoff_date=self.cutoff_date,
            limit=int(self.limit or 200),
            offset=int(getattr(self, "batch_offset", 0) or 0),
            commit_every=int(self.commit_every or 200),
        )

        # auto-advance if field exists
        if hasattr(self, "batch_offset"):
            self.batch_offset = res.get("next_offset") or self.batch_offset

        self._log("Fresh Rebuild Operator Deals (Batch)", res)
        return res

    @frappe.whitelist()
    def backfill_dates_from_state_history(self):
        from cclms.services.mirror.backfill_dates_from_state_history import run
        res = run(
            limit=int(self.limit or 0),
            commit_every=int(self.commit_every or 200),
            overwrite=int(self.overwrite or 0),
        )
        self._log("Backfill Dates From State History", res)
        return res
