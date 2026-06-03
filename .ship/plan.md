# Technical Plan: Affiliate Pages (Digistore24, curated-ID model)

Builds on verified facts in `spec.md` + `.ship/learnings.md`. Mirrors existing engine patterns so it slots in cleanly.

## Section 1: Architecture Integration
The existing engine abstracts everything behind small modules wired in `main.py` (`register_X(app)`), `scheduler.py` (APScheduler jobs guarded by `_safe` + readiness check), and `config.py` (`MANAGED_SETTINGS` + `_LiveSettings`). The affiliate track is a parallel, self-contained track that reuses: `db`, `llm` client, dashboard auth, the `pages/`-style static serving (like `home.py` serves landers), and the existing tracker concept.

Key design choice from verification: **no discovery**. Operator pastes IDs → `affiliate_products` rows. The promolink is built by formula (robust). `getMarketplaceEntry` enrichment is **best-effort** (never hard-fails a product).

## Section 2: Database Changes (append to `src/schema.sql`)
```sql
CREATE TABLE IF NOT EXISTS affiliate_products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      TEXT    NOT NULL UNIQUE,      -- Digistore24 numeric product id (from promolink)
    entry_id        TEXT,                          -- marketplace entry id if resolved (for getMarketplaceEntry)
    headline        TEXT    NOT NULL DEFAULT '',
    language        TEXT    NOT NULL DEFAULT '',
    currency        TEXT    NOT NULL DEFAULT '',
    commission_pct  REAL    NOT NULL DEFAULT 0.0,  -- affiliate_share
    epc             REAL    NOT NULL DEFAULT 0.0,  -- stats_affiliate_profit_visitor
    cancel_rate     REAL    NOT NULL DEFAULT 0.0,  -- stats_cancel_rate
    conversion_rate REAL    NOT NULL DEFAULT 0.0,
    stars           REAL    NOT NULL DEFAULT 0.0,
    score           REAL    NOT NULL DEFAULT 0.0,
    stats_ok        INTEGER NOT NULL DEFAULT 0,    -- 1 if getMarketplaceEntry resolved
    status          TEXT    NOT NULL DEFAULT 'candidate'
                            CHECK(status IN ('candidate','testing','winner','loser','excluded','paused')),
    rules_json      TEXT,
    first_seen      TEXT    NOT NULL DEFAULT (datetime('now')),
    last_checked    TEXT
);

CREATE TABLE IF NOT EXISTS affiliate_pages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id     TEXT    NOT NULL REFERENCES affiliate_products(product_id),
    slug           TEXT    NOT NULL UNIQUE,
    title          TEXT    NOT NULL DEFAULT '',
    file_path      TEXT    NOT NULL DEFAULT '',
    views          INTEGER NOT NULL DEFAULT 0,
    clicks         INTEGER NOT NULL DEFAULT 0,
    status         TEXT    NOT NULL DEFAULT 'live'
                           CHECK(status IN ('live','paused')),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_aff_pages_slug ON affiliate_pages(slug);
```
`init_db()` already runs `schema.sql` on boot (idempotent `CREATE TABLE IF NOT EXISTS`), so no migration script needed.

## Section 3: Client — `src/clients/digistore24.py`
Mirror `cpa.py` style (httpx, typed errors, `settings`).
- `BASE = "https://www.digistore24.com/api/call"`, header `X-DS-API-KEY`.
- `parse_product_id(line: str) -> str | None` — accept bare numeric id, or extract from `…/redir/{id}/…` or any URL containing the id.
- `get_user_info()` → used to auto-resolve the affiliate name (`user_name`) if `DIGISTORE24_AFFILIATE_NAME` unset.
- `get_marketplace_entry(entry_id) -> dict | None` — returns None on "not found"/403 (best-effort; never raises for missing).
- `build_promolink(product_id, affiliate_name, campaign_key) -> str` → `https://www.digistore24.com/redir/{product_id}/{affiliate_name}/{campaign_key}`.
- Thin auth check helper reused by `is_engine_configured`-style gating.
- ⚠️ Open item to resolve at implementation with a REAL pasted id: how to map product_id → entry_id for `getMarketplaceEntry`. If no clean mapping, leave `entry_id` null, `stats_ok=0`, and rely on the live ad test (design already tolerates this).

## Section 4: Research/validate — `src/affiliate_research.py`
- `add_products(raw_lines) -> dict` — parse each line → product_id → upsert `affiliate_products` (status candidate, preserve existing). Returns {added, skipped, invalid}.
- `validate_and_enrich()` — for each candidate: try `get_marketplace_entry`; if resolved, fill stats, set `stats_ok=1`, compute `score = commission_pct * max(epc, 0.01)`, and auto-`excluded` when `commission_pct < MIN_COMMISSION` or `cancel_rate > MAX_CANCEL_RATE` or name/headline hits existing `offers._BLOCKED_PATTERNS`. If unresolved, keep candidate, log "stats unavailable". Never raise.
- `pick_next_product()` — highest score candidate (mirror `offers.pick_next_offer`).

## Section 5: Page generation — `src/affiliate_generate.py`
Mirror `generate.py`'s LLM usage (`src/clients/llm.py`, model from `settings.llm_model`).
- `generate_page(product_row)` → LLM returns JSON sections (title, meta_desc, h1, what_is, how_it_works, benefits, pros[], cons[], who_for, pricing, verdict, faq[]). Render `affiliate_review.html` → write `pages/{slug}.html` → insert `affiliate_pages`. Slug from headline (kebab, deduped).
- Page CTA points to `/aff/{slug}` (not the promolink directly) so clicks are counted first.

## Section 6: Routes — `src/affiliate_routes.py` + dashboard
- `register_affiliate_routes(app)` (called from `main.py`):
  - `GET /p/{slug}` → serve `pages/{slug}.html`, `views += 1`, 404 unknown/paused.
  - `GET /aff/{slug}` → `clicks += 1`, 302 to `build_promolink(product_id, affiliate_name, slug)`.
- Dashboard (`src/dashboard.py`): new authed handlers
  - `POST /dashboard/products` → `affiliate_research.add_products(textarea)` then redirect back.
  - Render a **"Products to promote"** panel in `dashboard.html`: textarea + Save + collapsible **inline explainer** (condensed `HOW-TO-PICK-PRODUCTS.md`: marketplace → pick by rules → copy link → paste; cheat-sheet commission 50%+, low cancel, auto-approve, $30–90, avoid grey/scam) + a live list of products (id, headline, commission, cancel rate, status, page status, "stats unavailable" tag).

## Section 7: Config — `src/config.py`
Add `_LiveSettings` properties + `MANAGED_SETTINGS` rows + resolve helpers:
- `DIGISTORE24_API_KEY` (reuse the already-set `DIGISTORE` env as fallback in the resolver), `DIGISTORE24_AFFILIATE_NAME` (default: auto from `get_user_info().user_name`), `DIGISTORE24_MIN_COMMISSION` (50), `DIGISTORE24_MAX_CANCEL_RATE` (15).
- `has_digistore()` + fold into engine-readiness so the affiliate scheduler jobs idle until the key is present (same pattern as `has_cpa`). Affiliate track is independent of CPA readiness.

## Section 8: Scheduler — `src/scheduler.py`
Two new `_safe` jobs, gated on `config.has_digistore()`:
- `affiliate_validate_job` (every 6–12h): `validate_and_enrich()`.
- `affiliate_pagegen_job` (daily): generate pages for candidates that have none yet (cap N/day to respect LLM budget).
(PropellerAds campaign creation toward `/p/{slug}` reuses the existing launch/optimize machinery in a later iteration; MVP gets pages live + tracked.)

## Section 9: File Map
Create: `src/clients/digistore24.py`, `src/affiliate_research.py`, `src/affiliate_generate.py`, `src/affiliate_routes.py`, `src/templates/affiliate_review.html`.
Modify: `src/schema.sql` (2 tables), `src/config.py` (keys+thresholds), `src/main.py` (register routes), `src/scheduler.py` (2 jobs), `src/dashboard.py` (products panel + POST), `src/templates/dashboard.html` (panel + explainer).
Keep: `spike/check_digistore24.py`, `HOW-TO-PICK-PRODUCTS.md`.
Tests: extend smoke tests (TestClient boot, `/p/{slug}` 404, `parse_product_id` units, `build_promolink` format).

## Risks / open items
1. `entry_id` ↔ `product_id` mapping for `getMarketplaceEntry` — resolve with one real pasted product; design tolerates failure (best-effort).
2. Auto-approve detection — may not be exposed per product via API; fallback = operator follows the pick guide (auto-approve column on the marketplace site) + the live test catches dead links.
3. Promolink for a non-partnered product may bounce — surface link health in the dashboard product list.
