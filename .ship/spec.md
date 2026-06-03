# Feature Spec: Affiliate Pages (Digistore24, curated-ID model)

## Feature Summary
A revenue track where the operator pastes a short list of **Digistore24 product IDs/links** into the dashboard, and the engine autonomously does the rest: builds a promotion page per product, drives **PropellerAds** traffic to it, tracks clicks → conversions via Digistore24's postback (IPN), and kills losers / scales winners based on **real ad-test results**. Pages double as paid-traffic landers and accrue organic SEO over time.

## Problem Statement
The CPA-network track is blocked (MyLead rejected the account). We need an instant-access, autonomous-via-API product source.

**Verified 2026-06-03 against the live Digistore24 API + official OpenAPI spec:** neither ClickBank nor Digistore24 expose an affiliate **product-discovery** API. Digistore24's `listMarketplaceEntries` lists *the vendor's own* products (returns 0 for our affiliate account); there is no `search`/`browse` endpoint anywhere in its 130+ functions. **Conclusion: autonomous product DISCOVERY via API is not possible.** Everything downstream of *having a product ID* IS automatable.

**Chosen model:** the operator curates a few product IDs by hand (5 min, occasional — guided by `HOW-TO-PICK-PRODUCTS.md`); the engine automates everything after that. ~95% hands-off, no scraping, no approval-rejection gate.

## Verified Facts (build on these, not guesses)
- Digistore24 classic API: `GET https://www.digistore24.com/api/call/{fn}`, header `X-DS-API-KEY: <key>`, JSON `{result, data}`. Auth confirmed (account `paidrew`, roles affiliate+merchant).
- **Promolink (the autonomous link — definitely works, formula-based):** `https://www.digistore24.com/redir/{product_id}/{affiliate_name}/{campaign_key}` — no per-click approval. `{affiliate_name}` = the account's Digistore24 ID.
- **Promotion requires an affiliate partnership per product.** Operator must pick **auto-approve** products (or accept the partnership once) so the promolink is live. ⚠️ confirm auto-approve detection per product during build.
- **Live stats (best-effort pre-filter):** `getMarketplaceEntry(entry_id)` returns `affiliate_share` (commission %), `stats_affiliate_profit_visitor` (EPC), `stats_affiliate_profit_sale`, `stats_cancel_rate`, `stats_conversion_rate`, `stats_stars`, `stats_seller_rank`, `stats_is_valid`, price, currency, language, headline, description. ⚠️ `entry_id` ≠ the product ID in a promolink, and access for non-owned products is UNCONFIRMED. Treat as best-effort: if a pasted product resolves and returns stats, use them to auto-drop bad picks; if not, skip the pre-filter and rely on the live ad test.
- **Conversion tracking = Digistore24 IPN/postback** to the engine's tracker (the real judge of winners/losers). Not dependent on getMarketplaceEntry.

## User Stories

### Story 1: Operator pastes products (dashboard input)
**As** the operator,
**I want** a box on the dashboard to paste Digistore24 product links or IDs,
**So that** I choose what to promote without touching code.

**Acceptance Criteria:**
- [ ] Dashboard has a "Products to promote" textarea: one product link or ID per line
- [ ] Accepts a full link (`…/redir/{id}/…` or a marketplace/product URL) OR a bare numeric ID; the ID is extracted automatically
- [ ] On Save, each ID is upserted into `affiliate_products` with status `candidate`; existing rows preserve status
- [ ] Invalid/blank lines are ignored with a visible note; duplicates de-duped
- [ ] Per-product live status shown back (see Story 5)

### Story 2: Automated validation + enrichment (best-effort)
**As** the engine,
**I want** to enrich each pasted product and drop obviously bad ones before spending ad money,
**So that** the operator's pick gets a second safety check.

**Acceptance Criteria:**
- [ ] For each candidate, attempt `getMarketplaceEntry` to fetch commission, EPC, cancel rate, conversion, stars
- [ ] If stats resolve: auto-mark `excluded` when commission < min (default 50%) OR cancel rate > max (default 15%) OR clearly grey/banned niche (reuse existing `_BLOCKED_PATTERNS`)
- [ ] If stats DON'T resolve (entry not accessible): keep as `candidate`, log "stats unavailable — relying on live test", do NOT hard-fail
- [ ] Opportunity score = commission × EPC when available, else commission only
- [ ] Rules/notes stored as JSON on the product row

### Story 3: Automated Page Generation
**As** the engine,
**I want** to generate a promotion page per candidate product,
**So that** there's a lander for paid traffic (and SEO over time).

**Acceptance Criteria:**
- [ ] LLM writes page sections: title, meta_desc, h1, what_is, how_it_works, benefits, pros, cons, who_for, pricing, verdict, faq (3-5)
- [ ] Rendered into `affiliate_review.html`, saved to `pages/{slug}.html`
- [ ] Row inserted into `affiliate_pages`
- [ ] Indexed (robots: index,follow), canonical URL, Schema.org Review + FAQPage
- [ ] Affiliate disclosure in top bar and footer

### Story 4: Page Serving + Click Tracking
**As** a visitor,
**I want** to read the page and click through to the product,
**So that** conversions attribute back to the page.

**Acceptance Criteria:**
- [ ] GET `/p/{slug}` serves the pre-generated HTML; view count incremented
- [ ] CTA links to `/aff/{slug}`
- [ ] GET `/aff/{slug}` increments click count, then 302-redirects to the Digistore24 promolink (`/redir/{product_id}/{affiliate_name}/{slug}` — slug as campaign key for attribution)
- [ ] 404 for unknown slugs

### Story 5: Dashboard Visibility
**As** the operator,
**I want** to see each product's status and page performance,
**So that** I know what's live and converting.

**Acceptance Criteria:**
- [ ] Products section shows: id, headline, commission, cancel rate, score, status (candidate/testing/winner/loser/excluded), page status, "stats unavailable" flag where applicable
- [ ] Per-page stats: views, clicks
- [ ] Manual pause (status=paused) stops a product/page

### Story 6: Settings Configuration
**As** the operator,
**I want** Digistore24 keys in the dashboard Settings,
**So that** no redeploy is needed.

**Acceptance Criteria:**
- [ ] `DIGISTORE24_API_KEY` and `DIGISTORE24_AFFILIATE_NAME` in MANAGED_SETTINGS (reuse the existing `DIGISTORE` env value already set)
- [ ] Engine idles gracefully if keys not set (existing pattern)
- [ ] `DIGISTORE24_MIN_COMMISSION` and `DIGISTORE24_MAX_CANCEL_RATE` configurable

## Technical Requirements
- New SQLite tables: `affiliate_products`, `affiliate_pages`
- New client: `src/clients/digistore24.py` (`get_marketplace_entry`, `build_promolink`, ID/link parsing)
- New module: `src/affiliate_research.py` (validation + enrichment of pasted IDs)
- New module: `src/affiliate_generate.py` (page generation)
- New template: `src/templates/affiliate_review.html`
- New routes: `src/affiliate_routes.py` (`/p/{slug}`, `/aff/{slug}`) + dashboard input handler
- Scheduler: jobs for validate+enrich and daily page-gen for new candidates
- Pages saved to `pages/`
- Keep verification spike `spike/check_digistore24.py`

## UI/UX Requirements
- Dashboard: "Products to promote" textarea + Save + live per-product status list
- **Inline explainer panel** right next to the textarea (so the operator is self-serve, no external docs needed): short steps = (1) open the Digistore24 marketplace, (2) pick products by the rules, (3) copy the product link, (4) paste here one per line. Include a condensed "pick the best" cheat-sheet (commission 50%+, low cancel rate, auto-approve, $30–90, avoid scammy/grey niches) — same content as `HOW-TO-PICK-PRODUCTS.md`, shown collapsible.
- Promotion page: light theme, max 720px column, star rating, Quick Verdict card + CTA, pros/cons grid, FAQ, disclosure bar+footer, mobile responsive
- See `.ship/design-notes.md`

## Integration Points
- `src/clients/llm.py` (page copy), `src/db.py`, `src/config.py` (MANAGED_SETTINGS), `src/scheduler.py`, `src/main.py`, `src/schema.sql`, existing dashboard, existing PropellerAds engine, existing tracker (click→conversion)

## Out of Scope (MVP)
- Autonomous product discovery (not possible via API — operator curates IDs)
- Scraping the marketplace
- Other networks (ClickBank/JVZoo/Amazon/CJ/Awin)
- Promoting products that need manual per-vendor approval (auto-approve only)
- A/B page variants, image scraping, email capture, comments, internal linking

## Success Criteria
- Operator can paste IDs/links in the dashboard and they become candidates
- Engine builds working promolinks and promotion pages with no code edits
- Bad picks auto-dropped when stats are available; otherwise judged by the live ad test
- Click tracking works end-to-end (`/aff/{slug}` → Digistore24 promolink with campaign key)
- Dashboard shows product list + page stats
- Keys configurable from Settings without redeploy
