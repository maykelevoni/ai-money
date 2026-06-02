# Task 011: Optimizer loop (the core proof)

## Description
The autonomous decision engine: pull fresh spend, compute ROI per campaign/zone/creative, then blacklist/pause/scale/kill — with minimum-sample gates so a $100 budget isn't burned on noise. Every decision logged. (Plan Section 6.)

## Files
- `src/optimize.py` (create)
- `tests/test_optimize.py` (create)

## Requirements
1. `run_optimizer()` for each active campaign:
   - Pull `clients.traffic.get_zone_stats`, upsert `spend_snapshots`, record spend in `budget.py`.
   - **Budget guard first:** if global/daily exhausted → pause all + Telegram alert + stop.
   - **Zone blacklist:** spend ≥ 1.5×payout AND 0 conv AND clicks ≥ MIN_ZONE_CLICKS → `exclude_zone`.
   - **Creative pause:** clicks ≥ MIN_CREATIVE_CLICKS and bottom-tier CTR/ROI → pause.
   - **Scale winner:** conv ≥ MIN_CONV and rolling ROI ≥ SCALE_ROI → raise daily_cap one step (≤ remaining global).
   - **Kill loser:** spend ≥ KILL_SPEND and ROI ≤ KILL_ROI → pause campaign, mark offer `loser`.
2. Every action writes a `decisions` row with reason + data_json.
3. All thresholds read from config. Core decision functions are pure (take stats, return actions) so they unit-test without live APIs.

## Existing Code to Reference
- `src/budget.py` (Task 004), `src/clients/traffic.py` (Task 005), `src/db.py`.
- `.ship/plan.md` Section 6 (exact thresholds + ordering).

## Acceptance Criteria
- [ ] Tests on synthetic stats: blacklist/pause/scale/kill each trigger only at the right thresholds.
- [ ] No action fires below minimum-sample gates.
- [ ] Budget guard pauses everything when caps hit; every decision is logged.

## Dependencies
- Task 004, Task 005, Task 003

## Commit Message
feat: autonomous optimizer (blacklist/pause/scale/kill) with audit log
