# Task 012: Daily Telegram report

## Description
Compose and send the daily summary so the operator can watch the proof and decide when to top up budget. (Plan Sections 4, 5; spec Story 4.)

## Files
- `src/report.py` (create)

## Requirements
1. `send_daily_report()`: from the db, compute spend, revenue, ROI, budget remaining, top/worst campaigns, and the day's optimizer actions.
2. Clearly flag any campaign that is sustainably profitable as "PROFITABLE — scale me" (the proof signal + the cue to add budget).
3. Send via `clients.telegram.send` as readable Markdown.
4. Also expose `send_alert(text)` for cap-hit/critical pushes (reused by optimizer budget guard).

## Existing Code to Reference
- `src/clients/telegram.py` (Task 006), `src/db.py`, `src/budget.py`.
- spec.md Story 4 (what the report must contain).

## Acceptance Criteria
- [ ] Report includes spend, revenue, ROI, remaining budget, per-campaign breakdown, actions taken.
- [ ] Profitable campaigns are clearly flagged.
- [ ] Message delivers to Telegram; alert helper works.

## Dependencies
- Task 006, Task 003, Task 004

## Commit Message
feat: daily Telegram performance report + alerts
