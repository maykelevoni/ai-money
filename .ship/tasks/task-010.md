# Task 010: Tests — units + smoke

## Description
Cover the pure logic and a boot smoke test. No live network.

## Files
- `tests/test_digistore24.py` (create)
- `tests/test_affiliate_routes.py` (create)

## Requirements
1. Unit `parse_product_id`: numeric id, redir link, marketplace URL, blank/garbage → None.
2. Unit `build_promolink`: exact format with and without campaign key.
3. Unit `affiliate_research.add_products`: counts + dedupe + status preservation (in-memory/temp DB).
4. Smoke (TestClient, like existing tests): app boots; `GET /p/unknown` → 404; with a seeded page row + file, `GET /p/{slug}` → 200 and views increments; `GET /aff/{slug}` → 302 to a redir URL.
5. `get_marketplace_entry` network calls must be mocked or skipped when no key (mirror `spike` skip pattern) — tests must pass offline.

## Existing Code to Reference
- `conftest.py`, existing `tests/` (TestClient boot pattern, temp DB fixtures)
- `.ship/learnings.md` (TestClient smoke pattern, offline-safe testing)

## Acceptance Criteria
- [ ] `pytest -q` passes offline with no Digistore24 key set
- [ ] Route + parsing + intake covered

## Dependencies
- Task 003, 004, 007

## Commit Message
test: units for Digistore24 client/intake and affiliate route smoke
