# Task 014: Read-only dashboard

## Type
ui

## Description
A single live dashboard page so the operator can watch the engine work: budget, campaigns with ROI, and the optimizer's decision feed. (Plan Section 4.)

## Files
- `src/dashboard.py` (create)
- `src/templates/dashboard.html` (create)
- `src/static/dashboard.css` (create)

## Requirements
1. `GET /dashboard` (token-gated via DASHBOARD_TOKEN query/header): render live data from SQLite.
2. Components: budget bar (funded/spent/remaining, red near cap); campaigns table (offer, status, spend, revenue, ROI%, conv) with profitable rows highlighted green + "scale me" badge; decisions feed (reverse-chron, with reason text); offer pipeline counts.
3. Style: dark, dense, monospace-ish, single CSS file, no JS framework. Auto-refresh every 30s (meta refresh or htmx).
4. Read-only — no actions/mutations from the UI.

## Existing Code to Reference
- `src/main.py`, `src/db.py`.
- `.ship/plan.md` Section 4 (component list + style).

## Acceptance Criteria
- [ ] `/dashboard` with valid token renders budget bar, campaigns table, decisions feed, pipeline.
- [ ] Profitable campaigns visibly highlighted with a scale badge.
- [ ] Page auto-refreshes; wrong/missing token is rejected.

## Dependencies
- Task 003, Task 004, Task 002

## Commit Message
feat: read-only live ops dashboard
