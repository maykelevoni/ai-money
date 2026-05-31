# ai-money: Autonomous Affiliate Arbitrage Engine

A self-running Python service that buys cheap push/pop traffic, sends it to
AI-generated landing pages for clean CPA offers, and optimizes campaigns
autonomously — killing losers, scaling winners, blacklisting bad zones.

**Traffic network:** PropellerAds (Advertiser API v5)  
**CPA network:** MyLead (preferred) / CPALead (fallback)  
**LLM:** Claude Haiku (landing-page copy + ad creatives)  
**Reports:** Telegram daily summary  
**Budget:** $100 seed, hard caps enforced in code + via API  

## Honest odds

~1-in-3 chance the first offer turns a profit. The engine's job is to cycle
offers cheaply until one does. The goal is **proof** — a single campaign where
`revenue > ad spend`, running hands-off — not big money.

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp config/.env.example config/.env
# Edit config/.env — fill in all keys and review thresholds

# 3. Run
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

For VPS deployment (systemd + Caddy HTTPS), see `SETUP.md`.

## Architecture

Single Python process: FastAPI + APScheduler in one service.

- **Scheduler jobs:** `launch_job` (daily), `optimize_job` (every 2–3h),
  `report_job` (daily), `budget_guard` (every 15min)
- **Core modules:** `offers`, `generate`, `launch`, `optimize`, `budget`, `report`
- **Tracker endpoints:** `/lp/{slug}`, `/go/{click_id}`, `/postback`
- **Dashboard:** `/dashboard` (token-gated, read-only)
- **DB:** SQLite (`data/engine.db`) — zero-config, no ORM

All money-moving actions route through `budget.py` so the spend cap is
enforced in exactly one place. Every optimizer decision writes an audit row
to the `decisions` table — visible on the dashboard and in daily reports.

## Safety rails

- `GLOBAL_BUDGET` + `DAILY_CAP` in `.env` enforced in code.
- Caps also mirrored on the PropellerAds API when campaigns are created.
- Hitting either cap pauses all spend and sends a Telegram alert immediately.
