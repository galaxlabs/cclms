# CCLMS Tracker + Follow-up Automation — Integration Blueprint

Sources studied:
- `E:\zara-ai-laptop-agent-main.zip` (Zara — Discord-controlled laptop AI agent: Claude brain + 38 tools: open_app, WhatsApp send, screenshot, keyboard/mouse via pyautogui, shell, files).
- `/home/fg/apps/xperts-crm/` (Node.js + Prisma CRM with Lead / FollowUp / Deal / Task / Campaign / Meeting / Document models + React frontend with LeadTracker, LeadsFollowUp, AgentFollowUp, CRMBoard, CalendarView).
- `github.com/galaxlabs/windows_tracker_client` (Windows tracker agent, v0.1.3).
- `cclms` Frappe app (ATM Leads, Tracker Device, esign integration).

## Goal

Reuse the **xperts-crm UI design** and the **Zara agent tool patterns** inside the **Frappe cclms** system:
1. Auto-scrape business info (from Google Maps / web) that meets criteria → feed as leads.
2. Auto-assign users to follow-up (round-robin by branch/department).
3. Auto-dial at the scheduled date/time (tracker agent pops the softphone and calls).
4. Follow-up schedule lists (portal page) + due dial tasks.
5. (Vision) Telegram + Slack notifications, no-setup auto-notify on lead/follow-up events.

## Implemented So Far

### cclms backend (Frappe)

- **`Follow-up Schedule` doctype** (`follow_up_schedule`): lead, business_name, business_phone, company, priority, follow_up_time, status (Scheduled/Due/Dialing/Completed/Missed/Cancelled), assigned_to (Sales Agent), assigned_branch, dialed_at, completed_at, notes, dial_result.
- **`cclms/api/follow_up.py`**:
  - `schedule_follow_up(lead_name, follow_up_time, priority, notes, assign)` — create a follow-up.
  - `auto_assign_due(company, branch)` — round-robin auto-assign due/unassigned follow-ups to enabled Sales Agents of the branch.
  - `due_follow_ups(agent, company, limit)` — due list for portal + tracker.
  - `next_dial_task(agent, company)` — single next due dial task for the tracker auto-dial.
  - `mark_dialed(name, result)` — tracker marks the call placed → status Dialing.
  - `complete_follow_up(name, result, notes)` → status Completed.
  - `my_follow_ups(agent, status, limit)` — current portal user's follow-ups (by their Sales Agent).
  - `_round_robin_pool(branch)` — enabled Sales Agents by branch.

### Windows tracker agent (cclms-tracker, v0.1.3 + session additions)

- `_auto_dial(phone)` — launches the system dialer via `tel:` URI (softphone registered for tel: scheme initiates the call). Zara-style best-effort UI dialing can be added later (focus window + click).
- `_poll_follow_up_dial(now)` — polls `cclms.api.follow_up.next_dial_task`; **busy-wait**: if `self.active_call` is set (a call is live), it skips and dials after the current call finishes. Respects the scheduled `follow_up_time` (skips future) and the **dial business-hours window + timezone**.
- `_within_dial_window(now)` — True only inside `follow_up_dial_start_hour`..`follow_up_dial_end_hour` in `follow_up_dial_timezone` (IANA, empty = system local). Defaults 9–21.
- Config (set on `Tracker Device`, delivered via policy → `bootstrap`): `follow_up_dial_enabled`, `follow_up_dial_start_hour`, `follow_up_dial_end_hour`, `follow_up_dial_timezone`, `follow_up_dial_poll_seconds` (default 30).

### Portal (btm.xperts-global.com)

- **Follow-up page** (`src/features/followup/followup-page.tsx`): schedule form (lead, datetime, priority, notes) + kanban board by status (Scheduled / Due / Dialing / Completed / Missed) with phone, time, priority, branch, agent; "Done" action. Reuses the xperts-crm kanban design.
- **Productivity page** already tracks idle/active + app-time by department.

### Follow-up-First Flow (approved design)

```
Google Maps / web  → scraper / browser extension  → cclms
   → Follow-up Schedule (prospect: business name, phone, address, source_url, priority, follow_up_time)
   → auto_assign_due (round-robin by branch)
   → tracker agent auto-dials at scheduled time (busy-wait if a call is live; business-hours + timezone aware)
   → positive call?  → convert_follow_up_to_lead(name, company, address...) → ATM Leads (Draft→Pending) + follow-up Completed
```

- `convert_follow_up_to_lead(name, company, workflow_state, address, city, state, state_code, zip_code, full_address)` — creates an ATM Lead from the follow-up's business data (falling back to follow-up fields), sets `executive_name = assigned_to`, links the follow-up back and marks it Completed. Inserts as **Draft** (workflow-valid) then moves to the requested state.

## ATM Leads "Duplicate for Companies" + Defaults (this session)

- `get_company_availability_for_location` now returns **only `active = 1`** Operator Companies and **excludes Bitcoin Depot** from the duplicate-target list.
- `ATM Leads.company` field: **Bitcoin Depot default removed**, `reqd = 1` → shows "Please select a company before saving this lead" on **save** (not on init).

## Verified (on btm.digihoopoe.com)

- schedule → auto_assign (round-robin to "Simon Johnson", Karachi) → due list → next_dial_task (phone returned) → mark_dialed → complete. Full loop works.
- Dup dialog returns 13 active companies, Bitcoin Depot excluded.
- Follow-up (with address) → convert → ATM Lead (Rocket Coin, Pending, full address), follow-up Completed + linked.

## Vision: Telegram + Slack (not yet built — documented)

- Add **`Notification Delivery Settings`** (single) doctype: telegram_bot_token, telegram_chat_id, slack_webhook_url, enabled.
- `cclms/utils/notify.py` → `notify(event, payload)`:
  - sends Telegram via `https://api.telegram.org/bot<token>/sendMessage`
  - posts Slack via webhook
- Trigger points (later):
  - Lead Approved / Rejected / Installed (own leads) → push to the lead's agent + partner.
  - Follow-up due → reminder to assigned agent.
  - Auto-dial placed / missed → result notification.
  - Agreement requested / signed → notify partner + operator.
- No-setup: tracker agent polls a `get_notify_config` and shows Windows popups (already has `_poll_notifications`); Telegram/Slack are global channel mirrors.

## Future Agent Capabilities (Zara-style reuse)

- **Scraping agent**: browser extension (maps.js already reads Google Maps place) → validate vs cclms criteria → create ATM Lead via `create_location`/`upsert_competitor_kiosk`.
- **Auto-assignment jobs**: Frappe scheduler every N minutes runs `auto_assign_due` + workflow-based assignment.
- **Auto-dialer**: agent `_auto_dial` extended to focus softphone (RingCentral/3CX) and click "Call" for reliable dialing; report outcome via `ingest_call` (call_outcome Talked/Not Answered/Missed).
- **Business-hours aware**: schedule follow-ups only within `Business Hours` per branch.

## How the Pieces Fit

```
Google Maps / web  → browser extension / scraper  → cclms (create lead, criteria check)
                                                        │
cclms scheduler  → auto_assign_due (round-robin by branch) → Follow-up Schedule (assigned agent)
                                                        │
Windows tracker agent  → polls next_dial_task  → _auto_dial(phone)  → softphone calls
                                                        │
                  ingest_call (outcome, duration) → Call Detail → productivity report by department
                                                        │
Telegram / Slack (vision)  ← notify()  ← lead/follow-up/call events
```
