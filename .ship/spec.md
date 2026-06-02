# Spec: Autonomous Affiliate Arbitrage Engine

> Feature: `autonomous-income-engine` · Project: `ai-money`
> Goal: prove AI can earn money autonomously on a VPS running 24/7, with the human only doing setup.

---

## Feature Summary

A self-running system on the user's VPS that makes money via **CPA affiliate arbitrage**: it buys cheap ad traffic, sends it to AI-generated landing pages promoting affiliate offers, and earns a payout each time a visitor completes the offer's action (a free signup / lead / install). The AI continuously reads performance data and **kills losing campaigns, scales winning ones, and blocks bad traffic** — the optimization loop a human media-buyer normally grinds by hand.

The win condition is not big money. It is a **single profitable campaign running hands-off**, proving the loop closes: money in (ad spend) < money out (affiliate revenue), with no human in the loop after setup.

---

## Problem Statement

"AI that makes money autonomously" mostly doesn't exist because money has gates AI can't pass alone (payouts, identity, platform ToS). The user accepts being the legal/financial wrapper and wants the AI to do all the *labor*. Prior options were rejected:
- SEO content sites → **too slow** (1–3 months to rank).
- Marketplace gigs → not fully passive.
- Trading bots → high risk of losing capital.

Paid-traffic affiliate arbitrage is the one model that is **fast** (paid traffic = instant visitors), **capped-risk** (hard daily/global budget limits, never loses more than funded), and **fully autonomous once running** (no customers, no fulfillment, no support — just an optimization loop).

---

## User Stories

### Story 1 — Setup (the only manual part)
**As the operator**, I do a one-time setup: create accounts on one CPA network and one traffic network, fund the traffic account, and drop API keys into a config file. After that I touch nothing.
- **Acceptance:** a documented setup checklist; the engine reads all credentials from a single `.env`/config; no code edits needed to run.

### Story 2 — Autonomous campaign creation
**As the engine**, I pull available CPA offers, pick promising ones (clean verticals only: free-trial / lead-gen / app-install), generate a landing page + ad creatives for each, and launch a small capped campaign on the traffic network — without human input.
- **Acceptance:** given valid API keys, the engine launches at least one live campaign end-to-end on a schedule, with spend capped at the configured daily limit.

### Story 3 — Autonomous optimization (the core proof)
**As the engine**, every N hours I read each campaign's spend vs. revenue per creative and per traffic source/zone, then **pause anything below the ROI threshold, scale winners, and blacklist bad zones** — automatically.
- **Acceptance:** optimizer runs on a cron; logs every decision (pause/scale/blacklist) with the data behind it; never exceeds the global budget cap.

### Story 4 — Visibility & the "add budget" signal
**As the operator**, I get a daily report (Telegram or email) and a simple read-only dashboard showing spend, revenue, ROI, and what the optimizer did — so I can watch the proof and decide when to top up the budget.
- **Acceptance:** a daily summary is delivered; a local dashboard shows live campaign stats; when a campaign is sustainably profitable it is clearly flagged as "scale me."

### Story 5 — Hard safety rails
**As the operator**, I am guaranteed the engine can never spend more than I funded.
- **Acceptance:** a global budget ceiling and per-day cap enforced in code *and* on the traffic network; if either is hit, the engine pauses all spend and notifies me.

---

## Technical Requirements

- **Runtime:** runs unattended on the VPS 24/7 (cron / scheduler + a long-running service).
- **Orchestration:** a **single standalone Python service** on the VPS (no n8n — the optimizer logic is more than glue and is cleaner as code). One readable codebase with a built-in scheduler; no node-graph tooling.
- **LLM:** cheap model (Claude Haiku or an open model) for landing-page copy, angles, and ad creatives — kept under the infra budget.
- **CPA network:** one beginner-instant-approval network with an API + conversion postbacks (candidates: CPALead, MyLead).
- **Traffic network:** one push/pop/native network that allows affiliate offers, has low minimums, and an Advertiser API (candidate: PropellerAds or similar).
- **Tracking:** a minimal self-hosted click→conversion tracker on the VPS (redirect + log + postback endpoint) to tie ad cost to affiliate revenue per campaign/creative/zone. No paid tracker for MVP.
- **Landing pages:** generated as static HTML, served from the VPS; fast-loading, mobile-first (push/pop traffic is ~mobile).
- **Config/secrets:** single config file / `.env`; no secrets in code.
- **Budget enforcement:** global + daily caps in code, mirrored by caps set via the traffic network API.

## UI/UX Requirements

- **Read-only local dashboard** (served from the VPS): table of campaigns with live spend / revenue / ROI / status, a feed of optimizer actions, and a clear "profitable — scale me" flag. Minimal, dark, dashboard-style; built fast, function over polish.
- **Daily report** pushed via **Telegram** (free bot API): spend, revenue, ROI, top/worst campaigns, actions taken, current budget remaining.

## Integration Points

- CPA network API (fetch offers, get tracking links, receive conversion postbacks).
- Traffic network Advertiser API (create/pause/scale campaigns, set budget caps, pull stats per zone/creative).
- LLM API (generate landers + creatives).
- Notification channel (Telegram Bot API).
- VPS (host the tracker, landing pages, dashboard, scheduler).

## Out of Scope (MVP)

- Multiple traffic networks or CPA networks (one of each first).
- Paid trackers (Voluum/Binom) and paid SEO tools.
- Google/Meta/Bing ads (they ban these offers).
- Sketchy verticals (sweepstakes "you won" content-lockers) — explicitly excluded.
- Building our own affiliate offers; tax/accounting automation; multi-user.
- Any guarantee of profit — see Success Criteria.

## Success Criteria

1. **Technical proof (must hit):** the full loop runs unattended on the VPS — fetch offer → generate lander+creatives → launch capped campaign → track clicks & conversions → optimizer pauses/scales/blacklists → daily report — with budget caps provably enforced.
2. **Financial proof (the goal, not guaranteed):** at least one campaign reaches **revenue > ad spend** sustained over several days, running hands-off. Honest expectation: ~1-in-3 chance the *first* offer is profitable; the engine's job is to cycle offers cheaply until one is.
3. **Safety proof:** across the whole run, total spend never exceeds the funded budget; hitting a cap pauses spend and notifies the operator.
4. **Autonomy proof:** after setup, zero manual intervention is required for the engine to keep operating and optimizing.
