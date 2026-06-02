# Task 007: Offer fetch, filter & selection

## Description
Pull offers from the CPA network, filter to CLEAN verticals within budget reach, persist them, and pick the next candidate to test. (Plan Sections 5, 6; spec "clean offers only".)

## Files
- `src/offers.py` (create)

## Requirements
1. `sync_offers()`: fetch via `clients.cpa.list_offers`, upsert into `offers` table with status `candidate`.
2. Filter rules: vertical in ALLOWED set (free-trial, lead-gen, email/zip submit, app-install); EXCLUDE sweepstakes / "you won" / content-locker / adult. Payout ≥ configured minimum. GEO in cheap-traffic allow-list.
3. `pick_next_offer()`: return the best untested `candidate` (e.g. highest payout), skipping `loser`/`excluded`.
4. `mark_offer(offer_id, status)` helper.

## Existing Code to Reference
- `src/clients/cpa.py` (Task 005), `src/db.py`, `src/models.py`.
- spec.md "Out of Scope" (excluded verticals).

## Acceptance Criteria
- [ ] `sync_offers()` populates the offers table with only clean verticals.
- [ ] Sketchy verticals are filtered out (unit-checkable with sample data).
- [ ] `pick_next_offer()` skips loser/excluded and returns the top candidate.

## Dependencies
- Task 005, Task 003

## Commit Message
feat: offer sync, clean-vertical filtering, and selection
