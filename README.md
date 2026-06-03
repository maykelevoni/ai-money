# ai-money: Autonomous Affiliate Arbitrage Engine

A self-running Python service that drives paid traffic to AI-generated pages for
affiliate/CPA offers and optimizes autonomously — killing losers, scaling
winners, blacklisting bad zones. Everything is configured and monitored from a
single dashboard; no redeploys to change keys or add products.

## Two revenue tracks

1. **Paid-traffic CPA engine** — buys cheap push/pop traffic from PropellerAds,
   sends it to AI-generated landers for clean CPA offers, and auto-optimizes.
2. **Digistore24 affiliate pages** — you paste a few Digistore24 product
   IDs/promolinks in the dashboard; the engine validates them, generates a
   promotion page per product (`/p/{slug}`), tracks click-throughs, and judges
   winners by the live ad-test.

> **Why curated IDs, not auto-discovery?** Verified against the live APIs:
> neither ClickBank nor Digistore24 expose an affiliate *product-discovery*
> API (Digistore24's `listMarketplaceEntries` returns only the *vendor's own*
> products). So discovery is a 5-minute manual pick; everything downstream is
> automated. The dashboard has a built-in pick guide.

**Traffic:** PropellerAds (Advertiser API v5) · **CPA:** MyLead / CPALead (fallback)
· **Affiliate:** Digistore24 · **LLM:** OpenRouter (`LLM_MODEL`, default
`google/gemini-2.0-flash-001`) · **Reports:** Telegram · **Budget:** $100 seed,
hard caps in code + via API.

## Honest odds

~1-in-3 chance the first offer turns a profit. The engine's job is to cycle
offers cheaply until one does. The goal is **proof** — a single hands-off
campaign where `revenue > ad spend` — not big money.

## Quick start (local / dev)

```bash
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/dashboard` (default password: `postforge`) and
enter your API keys on the **Settings** page. The engine idles until its keys
are set — no `.env` editing required (settings are stored in the DB).

## VPS deployment (production)

```bash
git pull origin main
sudo systemctl restart ai-money     # systemd unit: deploy/ai-money.service
```

First-time only: install the systemd unit + Caddy (HTTPS reverse proxy):

```bash
sudo cp deploy/ai-money.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now ai-money
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile   # edit: set your domain
sudo systemctl reload caddy
```

No DB migration step — `init_db()` runs `src/schema.sql` (idempotent) on boot.
After deploy, set keys (incl. `DIGISTORE24_API_KEY`) on the dashboard Settings
page.

## Dashboard

Token-gated at `/dashboard`. Tabs:

- **Overview** — KPI cards (funded / spent / remaining / campaigns / products /
  pages / conversions), engine status, the **Products to Promote** intake (with
  the pick-products guide), campaigns table, offer pipeline, and recent activity.
- **Pages** — every generated promotion page with views / clicks / CTR.
- **Activity** — a unified log of everything the system has done (products
  analysed, pages created, campaigns, optimizer decisions, conversions, budget).
- **Settings** — all API keys & thresholds, applied immediately (DB-backed).

## Architecture

Single Python process: **FastAPI + APScheduler**.

- **Scheduler jobs:** `launch_job` (daily), `optimize_job` (every 2–3h),
  `report_job` (daily), `budget_guard_job` (every 15m), `affiliate_validate_job`
  (~8h), `affiliate_pagegen_job` (daily)
- **CPA engine modules:** `offers`, `generate`, `launch`, `optimize`, `budget`, `report`
- **Affiliate track modules:** `clients/digistore24`, `affiliate_research`,
  `affiliate_generate`, `affiliate_routes`
- **Public routes:** landers + tracker, `/p/{slug}` (promotion pages),
  `/aff/{slug}` (click → Digistore24 promolink redirect)
- **DB:** SQLite (`data/engine.db`) — zero-config, no ORM

All money-moving actions route through `budget.py` so the spend cap is enforced
in one place. Optimizer decisions are written to the `decisions` table and
surfaced in the dashboard Activity log + daily reports.

## Safety rails

- `GLOBAL_BUDGET` + `DAILY_CAP` enforced in code and mirrored on the PropellerAds
  API when campaigns are created.
- Hitting either cap pauses all spend and sends a Telegram alert immediately.
- Affiliate offers are filtered to clean verticals; auto-approve products only.
