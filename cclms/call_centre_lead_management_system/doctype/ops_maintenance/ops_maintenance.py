import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


ALLOWED_HEAVY_ROLES = {"System Manager", "Director"}


def _has_heavy_access():
    return bool(set(frappe.get_roles()) & ALLOWED_HEAVY_ROLES)


class OpsMaintenance(Document):
    def _require_heavy_access(self):
        if not _has_heavy_access():
            frappe.throw("Only System Managers or Directors can run maintenance and AI batches.")

    def _write_log(self, title, result, status="Success"):
        self.last_run_log = f"{title}\n{frappe.as_json(result, indent=2)}"
        self.save(ignore_permissions=True)

        if frappe.db.exists("DocType", "Ops Run Log"):
            log = frappe.get_doc(
                {
                    "doctype": "Ops Run Log",
                    "action_type": title,
                    "status": status,
                    "requested_by": frappe.session.user,
                    "started_on": now_datetime(),
                    "finished_on": now_datetime(),
                    "batch_offset": int(self.batch_offset or 0),
                    "batch_limit": int(self.limit or 0),
                    "processed_count": result.get("processed") or result.get("processed_in_batch"),
                    "success_count": result.get("updated") or result.get("ok"),
                    "failed_count": result.get("fail"),
                    "skipped_count": result.get("skipped"),
                    "summary_json": frappe.as_json(result, indent=2),
                }
            )
            log.insert(ignore_permissions=True)
            self.last_run_log_ref = log.name
            self.save(ignore_permissions=True)

    @frappe.whitelist()
    def rebuild_deals_since_cutoff(self):
        self._require_heavy_access()

        from cclms.services.mirror.fresh_rebuild_operator_deals import run

        result = run(
            cutoff_date=self.cutoff_date or "2025-08-01",
            limit=int(self.limit or 200),
            offset=int(self.batch_offset or 0),
            commit_every=int(self.commit_every or 100),
        )
        self.batch_offset = result.get("next_offset") or self.batch_offset
        self._write_log("Rebuild Deals Since Cutoff", result)
        return result

    @frappe.whitelist()
    def backfill_dates_from_state_history(self):
        self._require_heavy_access()

        from cclms.services.mirror.backfill_dates_from_state_history import run

        result = run(
            limit=int(self.limit or 0),
            commit_every=int(self.commit_every or 100),
            overwrite=int(self.overwrite or 0),
        )
        self.batch_offset = result.get("next_offset") or self.batch_offset
        self._write_log("Backfill Dates From State History", result)
        return result

    @frappe.whitelist()
    def clean_enrich_from_zip_analytics(self):
        self._require_heavy_access()

        from cclms.services.zipintel.deal_enrichment import enrich_operator_deals

        result = enrich_operator_deals(
            limit=int(self.limit or 200),
            offset=int(self.batch_offset or 0),
            commit_every=int(self.commit_every or 100),
        )
        self.batch_offset = result.get("next_offset") or self.batch_offset
        self._write_log("Clean Enrich From Zip Analytics", result)
        return result

    @frappe.whitelist()
    def ai_enrichment(self):
        self._require_heavy_access()

        from cclms.services.ai.pipeline import run

        result = run(
            limit=int(self.ai_batch_size or self.limit or 25),
            offset=int(self.batch_offset or 0),
            force_gemini=int(self.force_gemini or 0),
        )
        self.batch_offset = result.get("next_offset") or self.batch_offset
        self._write_log("AI Enrichment", result)
        return result
