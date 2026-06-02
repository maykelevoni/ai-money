# Technical Plan: Autonomous Affiliate Arbitrage Engine

> Greenfield Python service on the VPS. Single codebase, SQLite, FastAPI + APScheduler.
> Read alongside `spec.md` and `context.md`.

---

## Section 0: Riskiest-thing-first (a spike before building)

The two external APIs are the project's biggest unknowns. **Before building the full engine**, the first task is a throwaway spike that confirms, for the *chosen* CPA + traffic networks:
- CPA network: can we fetch offers, get a tracking link, and receive conversion **postbacks**? (CPALead / MyLead)
- Traffic network: does the **Advertiser API** support create campaign, set/lower daily budget, pause campaign, and **exclude a zone/source**? (PropellerAds-style)

If a chosen network can't do these via API, autonomy breaks — we swap the network *now*, not after building. This de-risks everything downstream.

---

## Section 1: Architecture Integration

Greenfield. One always-on Python service with three logical layers:

```
                ┌─────────────────────────────────────────────┐
                │  scheduler (APScheduler, in-process)          │
                │   • launch_job   (daily)   → pick & launch    │
                │   • optimize_job (every 2-3h) → kill/scale    │
                │   • report_job   (daily)   → Telegram         │
                │   • budget_guard (every 15m) → hard caps      │
                └───────────────┬─────────────────────────────┘
                                │ calls
   ┌────────────────────────────┼──────────────────────────────┐
   │ core logic (pure-ish modules, unit-testable)               │
   │  offers.py  generate.py  launch.py  optimize.py  report.py │
   │  budget.py  (ledger + cap enforcement)                     │
   └───────────────┬───────────────────────────┬───────────────┘
                   │ reads/writes              │ HTTP
            ┌──────▼──────┐            ┌────────▼─────────┐
            │ SQLite db   │            │ external APIs    │
            │ (engine.db) │            │ CPA / traffic /  │
            └─────────────┘            │ LLM / Telegram   │
                   ▲                   └──────────────────┘
                   │ reads/writes
   ┌───────────────┴───────────────────────────────────────────┐
   │ web (FastAPI + uvicorn) — one process                      │
   │  tracker: /lp/{cid}  /go/{cid}  /postback                  │
   │  static landing pages (served from /landers)               │
   │  dashboard: /dashboard (read-only)                         │
   └────────────────────────────────────────────────────────────┘
```

**Single process** (FastAPI app starts APScheduler on startup) for MVP simplicity; run under **systemd** on the VPS for auto-restart. Splitting web vs. scheduler into two processes is a noted future step, not MVP.

**Patterns to follow:** keep core modules free of framework imports (take data in, return decisions out) so the optimizer logic is testable without hitting live ad networks. All money-moving actions route through `budget.py` so the cap is enforced in exactly one place.

**Deliberate non-adoption:** no paid tracker (Voluum/Keitaro/Binom) and no n8n. We build a ~100-line tracker instead — keeps recurring cost at $0 and the codebase readable, which matches the $100-total constraint.

---

## Section 2: Database (SQLite — `engine.db`)

Single file, zero-config, perfect for one VPS. Tables:

- **offers** — `id, network, network_offer_id, name, vertical, payout, geo, status(candidate|testing|winner|loser|excluded), tracking_url, first_seen, last_tested`
- **campaigns** — `id, offer_id, traffic_campaign_id, lander_path, status(pending|active|paused|killed), daily_cap, created_at, notes`
- **creatives** — `id, campaign_id, traffic_creative_id, title, description, icon_path, status(active|paused), clicks, ctr`
- **clicks** — `id, click_id(uuid), campaign_id, zone, cost, country, ts` (one row per visitor landing)
- **conversions** — `id, click_id, payout, ts` (one row per postback; joins to clicks → campaign/zone)
- **spend_snapshots** — `id, campaign_id, zone, spend, clicks, ts` (pulled from traffic API; source of truth for cost)
- **decisions** — `id, ts, scope(zone|creative|campaign|offer), target_id, action(pause|scale|blacklist|kill|launch), reason, data_json` (full audit trail of every autonomous action)
- **budget_ledger** — `id, ts, amount, kind(deposit|spend), running_total` (the spend cap source of truth)

ROI for any campaign/zone = `sum(conversions.payout) − sum(spend_snapshots.spend)`, sliced by the join on `click_id`/`zone`.

Migrations: a single `schema.sql` run on startup if tables absent (no migration framework needed for greenfield MVP).

---

## Section 3: API Design (internal web endpoints)

The web layer is mostly the **tracker**, plus the dashboard. All public-facing, no auth on tracker (must accept ad-network traffic); dashboard behind a simple token.

| Method | Path | Purpose |
|---|---|---|
| GET | `/lp/{campaign_slug}` | Serve the AI-generated landing page. Logs a `clicks` row using macros from query (`?zone=&cost=&country=&cid=`). Sets `click_id`. |
| GET | `/go/{click_id}` | CTA redirect. Appends `click_id` as subid to the offer's `tracking_url` and 302-redirects to the CPA offer. |
| GET/POST | `/postback` | CPA network calls this on conversion: `?subid={click_id}&payout={amount}`. Writes `conversions` row. Optional shared-secret param. |
| GET | `/dashboard` | Read-only HTML: campaigns table (spend/rev/ROI/status), decisions feed, budget remaining, "profitable — scale me" flags. Token-gated. |
| GET | `/health` | Liveness for systemd/monitoring. |

**Traffic-network macros:** landing page URL registered with the network as `https://DOMAIN/lp/{slug}?zone=${ZONE}&cost=${COST}&country=${COUNTRY}&cid=${CLICKID}` — exact macro names confirmed in the Section 0 spike.

---

## Section 4: Frontend (the dashboard — internal, minimal)

Not a marketing site → no external design refs. One server-rendered page (Jinja2), no SPA, no build step.

- **Style:** dark, monospace-ish, dense dashboard. Function over polish. Single CSS file, no framework (or tiny Pico.css).
- **Components on the one page:**
  - **Budget bar** — funded vs. spent vs. remaining; turns red near cap.
  - **Campaigns table** — offer, status, spend, revenue, ROI%, conversions; profitable rows highlighted green with a "scale me" badge.
  - **Decisions feed** — reverse-chron list of optimizer actions with the reason ("blacklisted zone 4471: $2.10 spent, 0 conv").
  - **Offer pipeline** — counts of candidate/testing/winner/loser offers.
- **Refresh:** auto-refresh every 30s (meta refresh or tiny htmx). No client state.
- Renders from the same SQLite the engine writes — always live.

---

## Section 5: Service Integration

- **CPA network:** REST API to list offers + get tracking links; **postback** at our `/postback`. **Verified:** CPALead has a JSON offers-feed API + postback ({subid}/{payout}/{ip_address}, IP whitelist) — but its catalog skews content-locking/gray, so for CLEAN offers prefer **MyLead** (or mainstream net), CPALead as fallback. Keys in `.env`.
- **Traffic network: PropellerAds (CONFIRMED + already funded by operator).** Advertiser/SSP API v5 verified to support every needed call: create/pause campaign, set/change daily budget+bid, whitelist/blacklist zones, per-zone stats. Self-serve API key. Operator already has a funded account ($24.47 + topping up $100), so the $100 min-deposit gate is already cleared. Build the `clients/traffic.py` wrapper modeled on `JanNafta/propellerads-mcp` client.py (Python reference impl with create/pause/clone, budget/bid, zone blacklist + dry-run, ROI analytics). Push/interstitial formats fit our clean offers.
- **LLM (Anthropic, cheap model):** `generate.py` calls Claude Haiku for landing-page copy + push creatives (title ≤ ~30 chars, desc ≤ ~45 chars). Icon image for MVP = a simple generated/stock icon (Pillow text-on-color or a small bundled icon set); real image optimization is post-MVP.
- **Telegram:** Bot API `sendMessage` for the daily report + any cap/alert pushes. Token + chat_id in `.env`.
- **VPS:** hosts the FastAPI process (systemd), SQLite file, landers, dashboard. Needs a domain pointed at it + HTTPS (Caddy or nginx+certbot — Caddy is one line, recommended).

---

## Section 6: Optimizer Logic (the core proof — detailed)

Runs every 2–3h. **Statistical-safety first**: never act below minimum sample sizes (small budgets = noisy data).

Per active campaign, after pulling fresh `spend_snapshots`:
1. **Budget guard (always first):** if `budget_ledger` running spend ≥ `GLOBAL_BUDGET` → pause ALL campaigns via API, Telegram alert, stop. If today's spend ≥ `DAILY_CAP` → pause until tomorrow.
2. **Zone blacklist:** any zone where `spend ≥ 1.5 × offer.payout` AND `conversions = 0` AND `clicks ≥ MIN_ZONE_CLICKS` → exclude zone via traffic API; log decision.
3. **Creative pause:** creative with `clicks ≥ MIN_CREATIVE_CLICKS` and CTR or ROI in bottom tier → pause; keep the best performers.
4. **Scale winner:** campaign with `conversions ≥ MIN_CONV` and rolling ROI ≥ `SCALE_ROI` (e.g. +20%) → raise `daily_cap` one step (e.g. +50%), capped by remaining global budget; log.
5. **Kill loser:** campaign with `spend ≥ KILL_SPEND` (e.g. 3× payout) and ROI ≤ `KILL_ROI` (e.g. −50%) → pause campaign, mark offer `loser`; `launch_job` will rotate to the next candidate offer.

All thresholds live in `config/.env` so behavior is tunable without code changes. Every branch writes a `decisions` row → full audit trail surfaced on the dashboard and in the daily report.

---

## Section 7: Tech Stack & Dependencies

- Python 3.11+
- **FastAPI** + **uvicorn** — web/tracker/dashboard
- **APScheduler** — in-process scheduling
- **httpx** — external API calls
- **anthropic** — LLM SDK (cheap model)
- **Jinja2** — lander + dashboard templates
- **python-dotenv** — config
- **Pillow** — MVP icon images
- SQLite via stdlib `sqlite3` + a thin `db.py` (no ORM needed)
- **Caddy** (system, not pip) — HTTPS reverse proxy
- **systemd** — keep the service alive

Total recurring cost: domain (~$10/yr) + LLM pennies + ad spend. Hosting $0 (existing VPS).

---

## Section 8: File Map

```
ai-money/
  README.md                 # what it is + the honest odds
  SETUP.md                  # the one-time manual checklist (accounts, keys, postback)
  requirements.txt
  config/
    .env.example            # every key + threshold documented
  src/
    main.py                 # FastAPI app + startup (schema init, scheduler start)
    config.py               # load + validate .env
    db.py                   # sqlite connection + helpers
    schema.sql              # table definitions
    models.py               # lightweight dataclasses for rows
    offers.py               # fetch/filter/select CPA offers
    generate.py             # LLM → landing page HTML + push creatives + icon
    launch.py               # create campaign + creatives on traffic network
    optimize.py             # the core kill/scale/blacklist loop (Section 6)
    budget.py               # ledger + global/daily cap enforcement (single chokepoint)
    report.py               # daily Telegram summary
    scheduler.py            # APScheduler job registration
    tracker.py              # /lp /go /postback route handlers
    dashboard.py            # /dashboard route + render
    clients/
      cpa.py                # CPA network API wrapper
      traffic.py            # traffic network Advertiser API wrapper
      llm.py                # Anthropic wrapper
      telegram.py           # Bot API wrapper
    templates/
      lander_base.html      # Jinja base for generated landers
      dashboard.html
    static/
      dashboard.css
  landers/                  # generated landing pages (gitignored)
  data/
    engine.db               # SQLite (gitignored)
  tests/
    test_optimize.py        # optimizer decisions on synthetic data (no live APIs)
    test_budget.py          # cap enforcement never exceeded
  spike/
    check_apis.py           # Section 0 throwaway validation script
```

---

## Open Questions / Risks (carried into build)

1. **Ad-creative moderation:** many traffic networks human-review new creatives → launch isn't instant (hours). Engine must handle `pending` campaigns gracefully. (Confirm in spike.)
2. **CPA account approval:** some networks require a short interview/phone verify. That's a setup-time human step (in SETUP.md), not an engine concern.
3. **API access tiers:** a network might gate the Advertiser API behind a deposit/min spend. Spike confirms before committing.
4. **GEO/payout fit for tiny budget:** need cheap-traffic GEOs whose offers still convert; `offers.py` filters will need tuning during the first live runs.
5. **Data noise on $100:** thresholds err toward *not* acting until min samples — accepting slower decisions to avoid burning budget on noise.
```
