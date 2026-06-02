# Task 009: Campaign launch

## Description
Take a selected offer + generated lander/creatives and launch a budget-capped campaign on the traffic network, registering the tracking URL with the right macros. Gated by budget.py. (Plan Sections 3, 5, 6.)

## Files
- `src/launch.py` (create)

## Requirements
1. `launch_campaign(offer)`: confirm `budget.can_spend(daily_cap)`; build the lander URL `https://{DOMAIN}/lp/{slug}?zone=${ZONE}&cost=${COST}&country=${COUNTRY}&cid=${CLICKID}` using the macro names from FINDINGS.md; call `clients.traffic.create_campaign` with a small `DAILY_CAP`; upload creatives; persist `campaigns` (status pending/active) + link creatives.
2. Set the traffic-network daily budget cap via API too (defense in depth — cap mirrored on their side).
3. Handle `pending` moderation state gracefully (campaign may not go live instantly); store status and let optimizer/report reflect it.
4. Never launch if global budget exhausted.

## Existing Code to Reference
- `src/clients/traffic.py` (Task 005), `src/budget.py` (Task 004), `src/offers.py`, `src/generate.py`.
- `spike/FINDINGS.md` for macro names + create-campaign params.

## Acceptance Criteria
- [ ] Launches a campaign with daily cap set on BOTH our side and the network.
- [ ] Tracking URL uses the confirmed macros.
- [ ] Refuses to launch when global budget is exhausted; records pending state correctly.

## Dependencies
- Task 005, Task 004, Task 007, Task 008

## Commit Message
feat: budget-capped campaign launch with tracking macros
