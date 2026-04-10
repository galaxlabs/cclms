# CCLMS Backend Intelligence API Design

## Goal

Provide a single backend-first intelligence layer for:

- browser extension
- Windows tracker client
- future Galaxy Smart Tool style UI

The frontend should stay light. Heavy work must live in CCLMS backend:

- duplicate checks
- ZIP analytics aggregation
- Google Maps and Gemini calls
- AI summaries
- caching

This avoids repeated heavy requests and keeps API keys off the frontend.

## Key Principles

1. Frontend should send small inputs and receive prepared answers.
2. Gemini and Google Maps calls should run only on the backend.
3. Cache ZIP-level and place-level intelligence aggressively.
4. Reuse the same backend methods across extension, tracker, and web UI.
5. Use `Google Maps Settings` as the primary source for Google keys and related config.

## Configuration Source

Primary settings:

- `Google Maps Settings.api_key`
- optional backend Gemini key:
  - `frappe.conf.gemini_api_key`
  - or a future secure field in `Google Maps Settings`

Recommended helper functions:

- `get_google_api_key()`
- `get_gemini_api_key()`
- `get_maps_intelligence_settings()`

The frontend must never call Gemini directly with an exposed key.

## Core Backend APIs

### 1. Map Decision Panel

Method:

- `cclms.api.browser_extension.get_map_decision_panel`

Purpose:

- return a lightweight decision payload for a Google Maps place
- support browser extension and future map UI

Input:

```json
{
  "place": {
    "business_name": "Mom's Kitchen",
    "address": "650 E Horizon Dr, Henderson, NV 89015, United States",
    "zip_code": "89015",
    "city": "Henderson",
    "state": "NV",
    "category": "Restaurant",
    "coordinates": {"lat": 36.027, "lng": -114.964},
    "opening_hours": "Friday 7 AM-3 PM"
  },
  "device_id": "WIN-01",
  "employee": "EMP-0001"
}
```

Output:

```json
{
  "message": {
    "context_type": "business_place",
    "prefill": {},
    "validation": {},
    "control_panel": {
      "zip": {},
      "lead_scope": {},
      "ai": {}
    },
    "crm_base_url": "https://crm.example.com"
  }
}
```

Rules:

- keep working hours in `prefill`
- do not show working hours in the map panel UI
- duplicate logic:
  - exact normalized address match is required
  - if both sides have business name, names must also match
  - if business name is missing on one side, address match can still count

### 2. Prefill ATM Lead Context

Method:

- `cclms.api.browser_extension.prefill_atm_lead_context`

Purpose:

- return parsed, normalized lead data for ATM Lead creation

Responsibilities:

- clean address
- split `address`, `city`, `state`, `state_code`, `zip_code`, `country`
- map category to `Business Types`
- include `opening_hours` / `hours`
- return creation route

Important:

- `opening_hours` is for child-table or field prefill use
- UI does not need to render hours in the map controller card

### 3. ZIP AI Summary

Method:

- `cclms.api.intelligence.get_zip_ai_summary`

Purpose:

- provide a cached Gemini summary for one ZIP
- optionally tailor the summary to a specific place context

Input:

```json
{
  "zip_code": "89015",
  "business_name": "Mom's Kitchen",
  "business_type": "Restaurant",
  "address": "650 E Horizon Dr"
}
```

Output:

```json
{
  "message": {
    "zip_code": "89015",
    "provider": "gemini",
    "summary": "Short market summary",
    "next_action": "Suggested next action",
    "caution": "Key warning",
    "foot_traffic_estimate": "Estimated foot traffic note",
    "suitability_note": "Why this place/ZIP is good or weak",
    "raw_text": "Original model output",
    "cached": true,
    "generated_on": "2026-03-20 12:00:00"
  }
}
```

Suggested Gemini prompt output keys:

- `summary`
- `next_action`
- `caution`
- `foot_traffic_estimate`
- `suitability_note`

### 4. Dashboard Snapshot

Method:

- `cclms.api.intelligence.get_dashboard_snapshot`

Purpose:

- power a future Galaxy Smart Tool style intelligence dashboard

Output should include:

- total lead count
- green / light green / yellow / red ZIP counts
- top ZIP opportunities
- saturation alerts
- leads needing review
- operator load / agent load summary

### 5. CRM AI Query

Method:

- `cclms.api.intelligence.ask_crm_ai`

Purpose:

- provide a fast natural-language AI answer using a bounded CRM context

Input:

```json
{
  "question": "Which ZIPs should we target next for gas stations?",
  "filters": {
    "business_type": "Gas Station",
    "state_code": "NV"
  }
}
```

Output:

```json
{
  "message": {
    "answer": "Short answer",
    "sources": {
      "zip_codes": ["89015", "89101"],
      "lead_names": ["Lead-0001"]
    }
  }
}
```

Guardrails:

- use bounded context only
- slice data before prompting
- do not send the whole CRM database to Gemini

## Caching Strategy

### ZIP Cache

Cache key:

- `zip_ai_summary::{zip_code}`

Recommended TTL:

- 12 to 24 hours

Persist optional copy in:

- `Zip Code Analytics.demo_json`

Suggested future fields:

- `ai_summary`
- `ai_last_updated`
- `ai_provider`

### Place Panel Cache

Cache key:

- `map_panel::{normalized_business_name_or_blank}::{normalized_address}::{zip_code}`

Recommended TTL:

- 1 to 6 hours

Use when:

- extension opens same place repeatedly
- multiple users inspect same place

### Dashboard Cache

Cache key:

- `intelligence_dashboard_snapshot`

Recommended TTL:

- 5 to 15 minutes

### Query Cache

Cache key:

- `crm_ai_query::{hash(question + filters)}`

Recommended TTL:

- 15 to 60 minutes

Only cache read-only summaries.

## Background Refresh Plan

### Frequent

Every 5 to 10 minutes:

- refresh competitor counts
- refresh lead counts by ZIP
- refresh lightweight dashboard counters

### Daily

Once or twice per day:

- generate or refresh ZIP AI summaries for active ZIPs
- update stored `demo_json` / AI summary fields

### On Demand

Run immediately when:

- user clicks `Refresh Analysis`
- cache is missing or expired
- material data changed in the ZIP

## Schema Recommendations

### Reuse Current Fields

Use existing:

- `Zip Code Analytics.demo_json`
- `zip_score`
- `zone_color`
- `competitor_kiosks`
- `company_kiosks`
- `population`

### Optional Future Fields

For `Zip Code Analytics`:

- `ai_summary`
- `ai_next_action`
- `ai_caution`
- `ai_foot_traffic_estimate`
- `ai_suitability_note`
- `ai_last_updated`

For `ATM Leads`:

- keep `opening_hours` or child-table destination if needed for maps prefill

## Frontend Responsibilities

Frontend should only do:

- place selection
- panel rendering
- user actions
- light client-side filtering

Frontend should not do:

- direct Gemini calls
- direct Google Maps intelligence calls
- duplicate business logic
- expensive analytics calculations

## Reuse Plan From Galaxy Smart Tool

Useful to reuse as design patterns:

- `components/MapModule.tsx`
- `components/IntelligenceModule.tsx`
- `services/frappeService.ts`

Do not copy directly into production:

- `services/geminiService.ts`

Reason:

- it calls Gemini from the frontend
- CCLMS should move all AI work to backend methods instead

## Implementation Order

1. Stabilize `get_map_decision_panel`
2. Add `get_zip_ai_summary` with cache
3. Add `get_dashboard_snapshot`
4. Add `ask_crm_ai`
5. Reuse these APIs in:
   - browser extension
   - Windows tracker
   - future Galaxy Smart Tool web UI

## Immediate Next Build Steps

1. Add `cclms/api/intelligence.py`
2. Move ZIP AI summary logic into that module
3. Add cache helpers using `frappe.cache()`
4. Store refreshed AI ZIP results in `Zip Code Analytics`
5. Point browser extension map panel to backend AI summary only
6. Keep opening hours in prefill payload, not visible panel output
