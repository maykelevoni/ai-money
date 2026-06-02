# Ship Context Log

## Key Decisions
- **Model:** autonomous CPA affiliate arbitrage — buy cheap push/pop/native traffic → AI-generated landing pages → clean CPA offers → AI optimizer kills losers / scales winners. Chosen for fast + capped-risk + fully autonomous after setup.
- **Rejected models:** SEO content (too slow, 1–3 mo), marketplace gigs (not passive), trading bots (capital risk), Google/Meta/Bing ads (ban affiliate offers).
- **Stack:** single standalone **Python** service on the VPS. **No n8n** — user finds node sprawl messy and the optimizer is more than glue.
- **Reports:** Telegram bot (free).
- **Offer verticals:** CLEAN ONLY (free trials, lead-gen, app installs). Sketchy "you won a prize" / sweepstakes content-lockers explicitly excluded for reputational low-risk.
- **CPA network candidates:** CPALead / MyLead (instant approval, $20 min payout, API + postbacks).
- **Traffic network candidates:** PropellerAds-style push/pop/native (low ~$25 min, Advertiser API).
- **Tracker:** minimal self-hosted click→conversion logger on VPS (no paid tracker for MVP).

## Constraints
- **Budget:** $100 total seed (NOT monthly), scaled up by user as it proves profitable. Allocation: ~$15 infra (domain + LLM credits), ~$70 capped ad test ($5–10/day caps), ~$15 reserve. VPS hosting already owned.
- **Hard rule:** engine can NEVER spend more than funded — global + daily caps in code AND mirrored on the traffic network API.
- **Priorities:** fast > low-risk > (low ceiling acceptable). Goal is PROOF, not big money.
- **LLM:** cheap model (Haiku / open) for landers + creatives, kept under infra budget.

## Notes
- Honest odds given to user: ~1-in-3 the first offer is profitable; engine's job is to cycle offers cheaply until one is. First profitable hands-off campaign = the proof milestone.
- User: knows n8n, builds automations, wants honest no-hype assessments, prefers conversational clarification over big question batches.

## Verified API Research (2026-05-31, done at planning time)
- **PropellerAds Advertiser/SSP API v5** CONFIRMS every call the optimizer needs: create campaign, start/pause, change bid+budget, zone whitelist/blacklist, per-zone stats. Self-serve API key. Swagger: ssp-api.propellerads.com/v5/docs. Open-source reference impl exists: `JanNafta/propellerads-mcp` (Python, has client.py with create/pause/clone, budget/bid, zone blacklist w/ dry-run, ROI analytics) — use as a CODE REFERENCE, not a dependency.
- PropellerAds min deposit = $100 (card) — was a concern, but **RESOLVED: operator ALREADY has a funded PropellerAds account ($24.47 balance) and will top up $100.** So PropellerAds IS the chosen traffic network (best-verified API + reference client + already funded). Low-min alternatives (PopAds $10, HilltopAds $50) noted only as fallback if the account ever has issues.
- **DECIDED traffic network = PropellerAds.** Push/interstitial formats fit clean offers.
- **CPALead** CONFIRMED: JSON offers-feed API (`campaign_json_load_offers.php?id=AFFID&ua=&geoip=`, device/GEO targeting) + postback with {subid}/{payout}/{ip_address} macros + IP whitelist. BUT its catalog skews content-locking/incentive (gray). For genuinely clean offers prefer **MyLead** or a mainstream CPA net; keep CPALead as fallback. Clean-vertical filter (Task 007) is therefore essential, not optional.
- **Revised budget fit:** domain ~$1–12 (or free DuckDNS subdomain = $0), LLM ~$5 (Haiku pennies), traffic first deposit $10 (PopAds) or $50 (HilltopAds), rest as reserve to scale winners.
