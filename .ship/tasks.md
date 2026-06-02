# Feature Tasks: Autonomous Affiliate Arbitrage Engine
Generated: 2026-05-31
Total: 15 tasks

## Checklist
- [x] 001: API validation spike (prove CPA + traffic APIs before building)
- [x] 002: Project scaffold + config loader + /health
- [x] 003: SQLite schema, db helpers, row models
- [x] 004: Budget ledger + cap enforcement (+ tests)
- [x] 005: CPA + traffic network API clients
- [x] 006: LLM + Telegram clients
- [x] 007: Offer fetch, filter (clean only) & selection
- [x] 008: AI landing page + push creative generation [ui]
- [x] 009: Budget-capped campaign launch
- [x] 010: Tracker endpoints (/lp, /go, /postback)
- [x] 011: Optimizer loop — blacklist/pause/scale/kill (+ tests)
- [x] 012: Daily Telegram report + alerts
- [x] 013: Scheduler wiring (the always-on jobs)
- [x] 014: Read-only live dashboard [ui]
- [x] 015: VPS deployment (systemd + Caddy) + setup docs

## Notes
- Task 001 is a gate: if the chosen networks lack the required API calls, swap networks before continuing.
- 004 (budget) and 011 (optimizer) carry unit tests — they are the safety + proof core.
- Build order respects dependencies: scaffold → db → budget → clients → offers → generate → launch → tracker → optimize → report → scheduler → dashboard → deploy.
