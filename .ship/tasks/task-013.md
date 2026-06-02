# Task 013: Scheduler wiring (the always-on engine)

## Description
Register the recurring jobs that make the system autonomous, started on app boot. This is what makes it run 24/7 with no human. (Plan Section 1.)

## Files
- `src/scheduler.py` (create)
- `src/main.py` (modify — start scheduler on startup)

## Requirements
1. APScheduler jobs:
   - `launch_job` (daily): if active campaigns < target, `offers.sync_offers()` then `launch.launch_campaign(offers.pick_next_offer())`.
   - `optimize_job` (every 2–3h): `optimize.run_optimizer()`.
   - `report_job` (daily, fixed hour): `report.send_daily_report()`.
   - `budget_guard_job` (every 15m): if caps exhausted, pause all + alert.
2. Jobs are wrapped to log + swallow exceptions (one failing run must not kill the scheduler).
3. Scheduler starts in FastAPI startup event; intervals come from config (sane defaults).

## Existing Code to Reference
- `src/offers.py`, `src/launch.py`, `src/optimize.py`, `src/report.py`, `src/budget.py`.
- `src/main.py` (Task 002).

## Acceptance Criteria
- [ ] All four jobs register and appear in the scheduler on boot.
- [ ] A thrown exception in one job is logged and does not stop the scheduler.
- [ ] Intervals are configurable.

## Dependencies
- Task 007, Task 009, Task 011, Task 012

## Commit Message
feat: APScheduler jobs for launch/optimize/report/budget-guard
