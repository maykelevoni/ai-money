# Task 010: Tracker endpoints

## Description
The web tracker that ties ad cost to affiliate revenue: serve landers (logging clicks), redirect CTAs to the offer (carrying subid), and receive conversion postbacks. (Plan Section 3.)

## Files
- `src/tracker.py` (create)

## Requirements
1. `GET /lp/{slug}`: generate a `click_id` (uuid), write a `clicks` row (campaign, zone, cost, country from query macros), render the lander HTML with the CTA pointing to `/go/{click_id}`.
2. `GET /go/{click_id}`: look up the offer's `tracking_url`, append `click_id` as the subid param, 302-redirect to the CPA offer.
3. `GET|POST /postback`: params `subid` (=click_id) + `payout`; optional shared-secret check; write a `conversions` row joined to the click. Return 200 quickly.
4. Register these routes on the FastAPI app; mount `static/` and serve `landers/`.

## Existing Code to Reference
- `src/main.py`, `src/db.py`, `src/models.py`.
- `.ship/plan.md` Section 3 (endpoint table + macro URL).
- `spike/FINDINGS.md` (postback format).

## Acceptance Criteria
- [ ] Visiting `/lp/{slug}?zone=..&cost=..` logs a clicks row and serves the lander.
- [ ] `/go/{click_id}` redirects to the offer URL with subid attached.
- [ ] `/postback?subid=..&payout=..` records a conversion tied to the original click.

## Dependencies
- Task 003, Task 002, Task 008

## Commit Message
feat: click/redirect/postback tracker endpoints
