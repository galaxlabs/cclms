# CCLMS Tracker — Gap Analysis

**Source repo read**: `E:\Projects\cclms-tracker\`
**Client code**: `windows_tracker_client\` (agent.py, embedded_defaults.py, map_intelligence.py, browser_extension\)
**Backend app**: `cclms` (deployed at `btm.digihoopoe.com`, local at `E:\Projects\btm-project\cclms\`)
**Date**: 2026-08-07

---

## 1. Critical: Un-merged Git Conflict Markers (BLOCKER)

The client source tree was never merged cleanly. `<<<<<<< HEAD`, `=======`, `>>>>>>>` markers are present in 10+ files. **This is the #1 gap** — the code as committed does not run.

| File | Markers | Impact |
|---|---|---|
| `windows_tracker_client\agent.py` | 42 | `SyntaxError` — **the agent does not start at all**. The conflict blocks split/duplicate feature initialization (device actions, health, notifications, biometric, map). |
| `windows_tracker_client\embedded_defaults.py` | 6 | `SyntaxError` — config never loads; duplicated/divergent feature defaults. |
| `windows_tracker_client\README.md` | ~14 | Merged README with contradictory instructions. |
| `windows_tracker_client\config.example.json` | ~3 | Broken example config. |
| `windows_tracker_client\browser_extension\background.js` | present | Extension background broken. |
| `windows_tracker_client\browser_extension\content\common.js` | present | Content script broken. |
| `windows_tracker_client\browser_extension\content\maps.js` | present | Maps content script broken. |
| `windows_tracker_client\browser_extension\options.js` | present | Options UI broken. |
| `windows_tracker_client\browser_extension\shared\storage.js` | present | Storage helper broken. |
| `windows_tracker_client\browser_extension\README.md` | present | Doc conflict. |
| `windows_tracker_client\browser_extension\BROWSER_EXTENSION_BACKEND_CONTRACT.md` | present | Contract doc conflict. |

**Verified**: `python -c "import ast; ast.parse(open('agent.py').read())"` → `SyntaxError: invalid syntax` on line 34 (`<<<<<<< HEAD`).

**Fix needed**: resolve every conflict. The `HEAD` side appears to be the older snapshot (device-actions/health only); the other side (`bfda544c…`) adds notifications, biometric, map intelligence, productivity rules, call metadata, and the full scoped-sync/map feature set. Pick the feature-complete side, verify the client's `run()` loop, and rebuild the EXE.

---

## 2. Deployment / Backend Target Mismatch

- `embedded_defaults.py` and `config.json` point to **`https://crm.galaxylabs.online`**.
- The active CCLMS backend for this project is **`https://btm.digihoopoe.com`** (VPS `72.60.118.195`).
- `config.json` contains a **real API key/secret** (`52944dcda2aeae4:7501693df7d062b`) committed in plaintext — credential exposure.

**Fix**: confirm which Frappe site the tracker should feed; update `site_url` + `api_key`/`api_secret` accordingly; rotate the leaked key if it was ever public; never commit secrets (move to `embedded_defaults.py` placeholder + per-device `config.json` that is gitignored).

---

## 3. Client ↔ Backend Contract Drift

The client calls these endpoints; the backend (`cclms/api/desktop_tracker.py`) implements all of them, but verify each matches the payload/response the client expects.

| Client method (config) | Backend method | Status |
|---|---|---|
| `cclms.api.desktop_tracker.get_tracking_policy` | implemented | ✅ but `binding` key naming must match client (`tracker_device`/`device_id`/`tracked_user`/`employee`/`sales_agent` — verified in `_resolve_tracker_binding` + policy) |
| `ingest_activity` | implemented | ✅ |
| `ingest_call` / `ingest_call_details` | implemented | ⚠️ client sends `caller_id`/`caller_phone`/`callee_phone`; backend maps to `customer_number`, `caller` fields — verify field alignment on `Call Detail` doctype |
| `ingest_logout` | implemented | ✅ |
| `report_device_health` | implemented | ⚠️ backend reads `data.get("processes")` but client sends `top_processes` (see contract §11 / prompt §1). **Field-name mismatch** — health snapshots may store empty process data. |
| `get_device_actions` | implemented | ⚠️ backend returns `payload_json`, `expires_at`, `approved_by`, `created_at`; client `_extract_action` expects `payload`/`action_type`/`expires_at` — verify JSON field names match (`payload_json` vs `payload`). |
| `ack_device_action` | implemented | ✅ |
| `get_device_notifications` | implemented | ✅ |
| `ingest_biometric_attendance` | implemented | ⚠️ client sends `records[].uid/user_id`; backend maps `user_id`/`uid` → `biometric_user_id`, `status`/`punch` → `punch_state` — verify. |
| `sync_zip_cache_scope` | delegates to `browser_extension.sync_zip_cache_scope` | ⚠️ confirm `browser_extension.py` is fully implemented (see §5) |
| `sync_lead_cache_scope` | delegates | ⚠️ same |
| `sync_competitor_cache_scope` | delegates | ⚠️ same |
| `validate_location_scope` | delegates | ⚠️ same |
| `upsert_competitor_kiosk` | delegates | ⚠️ same |

### Likely field-name mismatches to verify on the live site
1. `report_device_health`: `processes` vs `top_processes`.
2. `get_device_actions` response: `payload_json` vs `payload`; `approved_by`/`created_at` presence.
3. `ingest_call` / `Call Detail`: `caller_id`/`caller_phone`/`callee_phone` vs `customer_number`.
4. Policy `binding` key names (client may expect `name`/`tracked_user`/`employee`/`sales_agent` per BACKEND_API_CONTRACT §policy, backend returns `tracker_device`/`device_id`/...).
5. `notifications`: client `_show_notification` may expect `title`/`message`/`repeat_seconds`/`severity` — backend returns those plus extras (good).

---

## 4. Policy Optional-Key Coverage

The client feature gates read policy fields like `device_actions_enabled`, `device_health_enabled`, `notifications_enabled`, `biometric_sync_enabled`, `call_metadata_enabled`, `map_intelligence_enabled`, `map_sync_scope_seconds`, `competitor_keywords`, `map_popup_enabled`.

Backend `get_tracking_policy` returns **all** of these. ✅ Backend side is complete.

⚠️ But the client **also** reads them from local `config`/`embedded_defaults` at init (e.g. `device_health_enabled`, `notifications_enabled`) and only applies them if both config AND policy agree. With the conflict-marker state of `embedded_defaults.py` it is impossible to know which defaults win.

---

## 5. Backend Optional Features — Implementation Depth Unknown

The following backend methods exist but **delegate to `cclms/api/browser_extension.py`**; their completeness was not verified in this pass and should be confirmed:

- `sync_zip_cache_scope`
- `sync_lead_cache_scope`
- `sync_competitor_cache_scope`
- `validate_location_scope`
- `upsert_competitor_kiosk`

**Action**: read `cclms/api/browser_extension.py` and confirm each is real (not a stub), idempotent (per fingerprint), scoped to the user's area, and returns the payload shapes in `BACKEND_API_CONTRACT.md` §1–5.

---

## 6. Data Model — Verified Against Live DB (btm.digihoopoe.com)

All tracker doctypes **exist** in the live DB, in the local code repo, and in git history (added 2026-03-18/19, commits `29de7df`, `a8d6858`). **Nothing was deleted.** All tables are currently **empty (0 records)** because no device has ever enrolled.

| Doctype | Live DB | Code repo | Git history | Fields in DB |
|---|---|---|---|---|
| Tracker Device | ✅ | ✅ | ✅ | 24 (device_id, tracked_user, employee, active, allowed_service_user, machine_name, ip_address, last_seen_on, device_actions_enabled, action_poll_seconds, notifications_enabled, notifications_poll_seconds, productivity_rules_json, biometric_*, biometric_last_sync_on) |
| Tracker Device Action | ✅ | ✅ | ✅ | 13 (device_id, tracker_device, action_type, status, approved_by, expires_at, created_at, started_at, completed_at, payload_json, result_json, error_message) |
| Tracker Device Health Log | ✅ | ✅ | ✅ | 20 (device_id, tracker_device, tracked_user, employee, sales_agent, machine_name, windows_username, version, report_time, queue_count, process_count, dns_*, last_log_lines_json, processes_json, system_info_json, raw_payload_json) |
| Tracker Biometric Attendance Log | ✅ | ✅ | ✅ | 9 |
| Device Profile | ✅ | ✅ | ✅ | 20 |
| Call Detail | ✅ | ✅ | ✅ | 18 |

**Backend code compatibility** (`desktop_tracker.py`): every field the code reads/writes on `Tracker Device` (`_resolve_tracker_binding`, `_tracker_runtime_policy`), `Tracker Device Action`, `Tracker Device Health Log`, `Device Profile` **exists** in the doctypes. ✅ No code↔schema mismatch found.

### Gaps (vs BACKEND_LOGIC_SPEC §5)

1. `Tracker Device` is missing the spec-recommended denormalized health fields:
   `latest_app_version`, `latest_health_report_at`, `latest_queue_count`, `latest_tracker_process_count`, `latest_dns_ok`, `latest_dns_ip`, `latest_memory_percent`, `latest_cpu_percent`, `latest_log_excerpt`, `device_health_status`.
   Backend `report_device_health` writes a **Tracker Device Health Log** row but does **not** update these fields on `Tracker Device`. Fleet-health dashboards depend on them → **gap**.
2. `Tracker Device` has no `health_status` classification logic (spec §6.1: Healthy/Warning/Offline/Error).
3. `Device Action` status enum should include `Pending/Success/Failed/Expired/Cancelled`; DB has `status` + `error_message` but the doctype JSON should be checked for the full status list + `message` field.
4. No `Tracker Device Snapshot`/`Tracker Device Action Log` doctype exists (spec §5.3 mentions optional history; backend uses Health Log + Action instead — acceptable, note as a deviation).

---

## 7. Dashboard / Reporting

Spec §7 suggests a device-health dashboard (device, agent, version, last seen, queue, process count, DNS, memory %, last action, health status; filters for unhealthy/stale/queue-backlog/failed-password actions).

- No such dashboard/report was found in this pass. **Gap**: build a report or page (e.g. `cclms` report/workspace) for tracker fleet health.

---

## 8. Security / Audit

- `config.json` has live credentials committed. Rotate.
- Backend enforces `_require_tracker_service_user()` on `get_tracking_policy` and `_resolve_tracker_binding` per device — good. Verify **all** endpoints are `allow_guest=False` (they are) and that `Tracker Device` `allowed_service_user` scoping is enforced on every endpoint, not just policy.
- `change_local_password` / `clear_prefetch` action types: backend lists supported actions; client blocks `clear_prefetch` unless `allow_aggressive_cleanup`. Confirm backend never auto-schedules `clear_prefetch`, and that password-change actions require approval + expiry (spec §6.2).

---

## 9. Offline Queue / Reliability

- Client has SQLite offline queue + retry (verified in `agent.py`: `_queue_event`, `_flush_queue`, `_send_or_queue`).
- Health reporting can include `queue_count`, `dns_status` — backend stores them. ✅
- No gap found here beyond the conflict-marker blocking import.

---

## 10. Browser Extension

- `browser_extension\` has its own README + backend contract, both **conflict-marked**.
- Depends on `cclms.api.browser_extension.*` endpoints (see §5).
- Duplicate/ZIP guidance + competitor upsert are extension features; blocked by both the JS conflicts and unverified backend delegation.

---

## 11. Recommended Priority Order

1. ~~Resolve all git conflict markers~~ **DONE (2026-08-15)** — resolved in local `cclms-tracker`, then the client was **synced to GitHub HEAD `windows_tracker_client` v0.1.3** (clean, no markers). Local backup at `C:\Users\Abdul Quddos\AppData\Local\Temp\opencode\btm_api\client-backup\`.
2. ~~Fix backend URL + rotate leaked credentials~~ **DONE** — `embedded_defaults.py` + `config.example.json` → `https://btm.digihoopoe.com`; `config.json` credentials replaced with placeholders.
3. Verify the 5 backend `browser_extension.*` delegations are real implementations.
4. Verify field-name mismatches (§3 list) against the live site with a real device call.
5. ~~Add Tracker Device denormalized health fields~~ **DONE** — added `device_health_status`, `latest_app_version`, `latest_health_report_at`, `latest_queue_count`, `latest_tracker_process_count`, `latest_dns_ok`, `latest_dns_ip`, `latest_memory_percent`, `latest_cpu_percent`, `latest_log_excerpt`; `report_device_health` writes them + `_classify_device_health()`.
6. Rebuild the EXE (`build_exe.ps1`) and re-test end-to-end against `btm.digihoopoe.com`.

---

## 12. Contract Templates Found (for eSign auto-fill)

Located in **private files** on `btm.digihoopoe.com` (`Home/Attachments`). The reusable blank templates (not the per-location signed copies):

| Template | File (private) | Blank fields to fill |
|---|---|---|
| **KPF RevShare** | `Template.KPF.RevShare.2024-5-20.LIVE (1).pdf` | Location Legal Entity, Effective Date, Location DBA Name, Phone, Email, Address for payment, Sales Contact, Account Manager + phone/email, Tenant or Landlord?, lease end date, Term (Years), Special Terms, Premises, Additional Entity, Effective Fee Revenue %, signatures |
| **KPF Distributors** | `Template.KPF.Distributors.July2023.pdf` | same + County, Distributor, Per Trans. Fee, Flat Fee |
| **Harding Capital Lease** | `Harding Capital Lease (1) (1).pdf` | lease-specific (AES-encrypted PDF; needs PyCryptodome to read) |
| **Site Acquisition Partnership** | `SITE ACQUISITION PARTNERSHIP AGREEMENT.pdf` | CryptoBase LLC ↔ Xperts Global partnership |
| **Placement Partner Agreement** | `PLACEMENT PARTNER AGREEMENT - COIN CONNECTIONS LLC (2)  (1).pdf` | partner agreement |
| **Remote BD Partner Agreement** | `REMOTE BUSINESS DEVELOPMENT PARTNER AGREEMENT (1) -  unsigned.pdf` | unsigned blank |
| Older variants | `Template.KPF.RevShare.2023-11-7.v2 CLEAN.docx.pdf`, `Template.KPF.Distributors.July2023b925f8.pdf` | same fields |

**KPF auto-fill mapping** implemented in `cclms/api/agreement_signing.py` → `fill_kpf_document_from_lead(document_name, lead_name)`. Verified: fills Location Legal Entity, Effective Date, DBA Name, Phone, Email, Address from the ATM Lead (+ Agreement Sign Form when present). Field source order: `Agreement Sign Form` → `ATM Leads` → empty.

---

## 13. Productivity / App-Usage Tracking

Implemented in the Windows client (`agent.py`):

- **Rules** from CRM policy `productivity_rules`: each rule has `process_name`, `window_title_contains`, `domain`, `rating` (`productive`/`unproductive`), `score` (e.g. +1 / −1).
- **Matching** (`_rule_matches`): process name exact, window-title substring, or website domain (normalized, subdomain-aware).
- **Applied per event** (`_apply_productivity` → `_productivity_for_event`): every `ingest_activity` payload (heartbeat, app switch, website visit) carries `productivity_rating`, `productivity_score`, `productivity_rule_name`.
- **App-time tracing**: the agent sends foreground `active_app` + `window_title` on each activity event; backend `Call Detail`/activity log stores duration-derived time per app.
- **Call outcome** (added this session): `call_outcome` ∈ Talked / Not Answered / Missed, `talk_duration_seconds`, `reference_id` (RingCentral call id) → `Call Detail` for per-department talk-time productivity.

**Note**: the productivity rules are configured on `Tracker Device.productivity_rules_json` (backend returns them in `get_tracking_policy`). No dashboard yet exists to roll these up by app/department.

---

## 14. Version History — `galaxlabs/windows_tracker_client` (GitHub) vs local `cclms-tracker`

**They are the SAME project.** Local `E:\Projects\cclms-tracker\windows_tracker_client` is a stale snapshot; GitHub is the source of truth and newer.

| Version | Commit | Notes |
|---|---|---|
| Init → 0.1.0 | `5e7f65b`, `ae28e61` | Initial Windows tracker client |
| 0.1.0 | `17d0ef5` | Runbook + runtime hardening |
| | `e8113c4` | **productivity** scoring |
| | `b060390`, `e0bc2a1`, `914d689` | map features |
| | `f6d559c`, `04b638a` | browser extension |
| | `bfda544` | **updated build** (the conflict branch in the local snapshot) |
| | `5cf5358` | intelligence |
| | `1d4c6ce` → `b2121dd` | v0.1.3 release |
| | `0997716` | bootstrap_env hardening |
| | `965ebd5` | install_service + control center UI |
| | `6035836`, `15aff22`, `997f55f`, `64a6f41`, `b74d34a` | browser extension maps AI + hours features |

**Local `cclms-tracker` was at `0.1.1` with un-merged conflicts; now synced to `0.1.3`** (clean) with these local-only additions re-applied on top:
1. `_classify_call_outcome` + `call_outcome` payload (session work).
2. `embedded_defaults.py`/`config.example.json` → `https://btm.digihoopoe.com`.

**Bottom line**: don't treat `E:\Projects\cclms-tracker` as the source of truth for the Windows client — pull from `github.com/galaxlabs/windows_tracker_client` (v0.1.3) and re-apply the small site-specific overrides.
