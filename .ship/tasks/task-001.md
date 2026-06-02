# Task 001: API validation spike

## Description
Throwaway script that PROVES the chosen CPA + traffic networks expose the API calls autonomy requires. This runs before any real build — if a network can't do these, we swap it now. (Plan Section 0.)

## Files
- `spike/check_apis.py` (create)
- `config/.env.example` (create — minimal: CPA + traffic keys only for now)

## Requirements
Networks are decided: **traffic = PropellerAds** (operator already funded; API v5 verified in research), **CPA = MyLead preferred / CPALead fallback** (clean offers). This task confirms credentials work and captures EXACT request/response schemas — not whether the capability exists (already confirmed).
1. Against the CPA network: list offers, fetch a tracking link for one offer, and capture the postback URL format ({subid}/{payout} macros).
2. Against PropellerAds SSP API v5 (auth with the operator's API key): list campaigns, and capture the exact request/response shape for: create campaign, set/lower daily budget, pause campaign, exclude a zone, pull per-zone stats. Model expectations on `JanNafta/propellerads-mcp` client.py.
3. Print PASS/FAIL per capability against the LIVE account (catches auth/permission/tier issues).
4. Capture the exact macro tokens PropellerAds passes (zone, cost, country, clickid) for the landing-page URL.

## Existing Code to Reference
- None (first task). Follow `.ship/plan.md` Section 0 + Section 5.

## Acceptance Criteria
- [ ] Script runs and prints PASS/FAIL for every required capability of both networks.
- [ ] Postback URL format and traffic macro names are written to `spike/FINDINGS.md`.
- [ ] If a capability is missing, FINDINGS.md states the recommended alternative network.

## Dependencies
- None

## Commit Message
chore: API validation spike for CPA + traffic networks
