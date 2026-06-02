# Task 005: CPA + traffic network API clients

## Description
Thin, typed wrappers around the two money-side APIs, informed by the Task 001 spike findings. These are the only modules that talk to those networks. (Plan Section 5.)

## Files
- `src/clients/cpa.py` (create)
- `src/clients/traffic.py` (create)

## Requirements
1. `cpa.py`: `list_offers(filters)`, `get_tracking_url(offer_id)`. Returns normalized dicts/dataclasses (not raw JSON).
2. `traffic.py`: `create_campaign(...)`, `add_creatives(...)`, `set_daily_budget(campaign_id, amount)`, `pause_campaign(campaign_id)`, `exclude_zone(campaign_id, zone)`, `get_zone_stats(campaign_id)`. Match the exact endpoints confirmed in `spike/FINDINGS.md`.
3. Use httpx with timeouts + basic retry on 429/5xx. Keys from `config.settings`.
4. No business logic here — wrappers only. Raise typed errors on failure.

## Existing Code to Reference
- `spike/check_apis.py` and `spike/FINDINGS.md` (Task 001 — authoritative for endpoints/macros).
- `src/config.py`.

## Acceptance Criteria
- [ ] All listed methods exist with typed signatures and normalized returns.
- [ ] Endpoints/params match FINDINGS.md.
- [ ] Network errors surface as typed exceptions, not raw httpx errors.

## Dependencies
- Task 001, Task 002

## Commit Message
feat: CPA and traffic network API clients
