### Call Centre Lead Management System

Call Centre Lead Management System

### What This App Does

`cclms` is a Frappe app for Bitcoin ATM / BTM location scouting, lead intake, operator submission tracking, ZIP-code analysis, competitor kiosk intelligence, and operations reporting.

Main working areas:

- Legacy lead intake in `ATM Leads`
- Timeline tracking in `ATM Lead State History`
- Derived deal tracking in `Operator Deal`
- Physical place tracking in `BTM Location`
- ZIP validation and scoring in `Zip Code Analytics`
- Competitor source-of-truth data in `Competitor Kiosk`
- Operations control and KPI reporting in `Ops Maintenance` and `ops-control-room`

### Key Features

- `ATM Leads -> Operator Deal` auto-sync on save
- Cutoff-aware rebuild logic for the new operator-deal system
- Timeline-driven milestone dates using `ATM Lead State History`
- Safe backfill mode using DB updates instead of strict live validation
- KPI APIs driven by milestone dates, not only current workflow state
- ZIP scoring and rule-based zone colors
- Competitor kiosk refresh using Google Places and OSM
- Validation hints for scouting and map workflows
- Browser notifications for workflow/email events
- Optional AI enrichment with local-first logic and Gemini fallback
- Windows desktop tracker for employee activity, attendance, browser visits, screenshots, and inferred call durations
- Daily call summary records and employee performance reporting

### Desktop Tracking

The app now includes a Windows-side tracker client outside the app folder in [`windows_tracker_client/`](/home/dg/dg-b/windows_tracker_client/README.md).

Backend tracking flow:

1. A Windows agent posts heartbeat events, browser visits, login/logout, screenshots, and inferred call sessions.
2. Frappe stores one `Employee Activity Log` parent row per employee per day.
3. Detailed events are stored in the `Activity Entry` child table.
4. Calls are stored in `Call Detail`.
5. Each day is rolled up into `Call Daily Summary`.
6. Attendance is marked through `Employee Checkin` when the first daily session starts.

Service-user security model:

1. Create a dedicated service role like `Tracker Agent`
2. Create a dedicated service user for the Windows tracker
3. Generate that service user's API key and secret
4. Enroll each laptop in `Tracker Device`
5. Map each device to:
   - tracked CRM user
   - employee
   - allowed service user
6. The tracker APIs only accept writes for enrolled devices and their assigned user/employee

Tracked data includes:

- user / employee
- machine and device information
- login and logout times
- active app and window title
- visited site URL and authorization status
- random screen snapshots
- total active minutes and idle minutes
- unauthorized site hits
- inferred or posted call durations

### Date-Driven Performance

Performance reporting is date-driven and does not depend on current `workflow_state`.

The system reads exact milestone fields from `Operator Deal`, including:

- `approved_date`
- `agreement_sent_date`
- `signed_date`
- `installed_date`
- `cancelled_date`

The new script report `Agent Performance Tracker` combines:

- signed / installed / approved / agreement-sent counts by month
- call totals and talk time
- attendance days
- active vs idle minutes
- unauthorized site counts

### Operator Deal Automation

The new deal layer does not replace `ATM Leads`. Instead:

1. `ATM Leads` remains the legacy intake/source record.
2. On save, the app can upsert:
   - `Operator`
   - `BTM Location`
   - `Operator Deal`
3. `Operator Deal` milestone dates are filled from:
   - `ATM Lead State History` first
   - lead `post_date` for `submitted_date`
   - current lead `modified` only as a fallback for the current mapped status when history is missing

Milestone fields currently supported:

- `submitted_date`
- `approved_date`
- `rejected_date`
- `needs_reanalysis_date`
- `agreement_sent_date`
- `signed_date`
- `converted_date`
- `install_scheduled_date`
- `installed_date`
- `cancelled_date`
- `disputed_date`

### ZIP And Competitor Intelligence

The app uses two different data roles:

- `Competitor Kiosk` is the live competitor source of truth
- `Zip Code Analytics` is the reusable validation/cache layer

Current intelligence flow:

1. Small scheduled batches scan competitor locations.
2. Competitor records are upserted in `Competitor Kiosk`.
3. ZIP caches are refreshed from competitor truth and scouting inputs.
4. Leads and deals can be validated using:
   - ZIP score / zone
   - same-ZIP lead spacing
   - competitor kiosk distance
   - 1-mile qualification threshold

### Scheduler

Current scheduled jobs include:

- daily state-history sync
- daily ZIP policy refresh
- every 5 minutes: ZIP + competitor intelligence batch

The 5-minute intelligence batch is designed to stay small to reduce quota/server load.

### Verification Commands

Backfill `Operator Deal` dates from `ATM Lead State History`:

```bash
bench --site crm.galaxylabs.online execute cclms.services.mirror.operator_deal_sync.backfill_dates --kwargs "{'limit':500,'offset':0,'overwrite':1}"
```

Rebuild deals from the system cutoff:

```bash
bench --site crm.galaxylabs.online execute cclms.services.mirror.operator_deal_sync.rebuild_from_cutoff --kwargs "{'cutoff_date':'2025-08-01','limit':100,'offset':0}"
```

Run one 5-minute intelligence batch manually:

```bash
bench --site crm.galaxylabs.online execute cclms.services.zipintel.intelligence.run_five_minute_intelligence --kwargs "{'batch_size':1,'ai_limit':0}"
```

Get scouting advice for one lead:

```bash
bench --site crm.galaxylabs.online execute cclms.call_centre_lead_management_system.page.atm_scouting.atm_scouting.get_location_advice --kwargs "{'lead_name':'YOUR-LEAD-NAME'}"
```

### Latest Verification Snapshot

Live verification run on `crm.galaxylabs.online` showed:

- before backfill:
  - total deals: `84`
  - with `submitted_date`: `84`
  - with `approved_date`: `10`
  - with `signed_date`: `14`
  - with `installed_date`: `4`
- after backfill + rebuild:
  - total deals: `101`
  - with `submitted_date`: `101`
  - with `approved_date`: `11`
  - with `signed_date`: `18`
  - with `installed_date`: `6`

Backfill result:

- `processed=84`
- `updated=84`
- `missing_lead=0`

Rebuild result:

- `processed_in_batch=100`
- `ok=98`
- `fail=0`
- `skipped=2`
- skipped reason: `missing_address_zip`

### Notes

- `ATM Leads` is still the intake system and should not be deleted.
- `Operator Deal` is the reporting and KPI layer.
- `Competitor Kiosk.actual_zip_code` should be preferred over fallback ZIP fields.
- Chrome/browser notifications require the user to be logged into Desk and to allow notification permission.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app cclms
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/cclms
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
