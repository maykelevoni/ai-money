# Task 004: Product intake, validation & enrichment

## Description
Turn pasted lines into `affiliate_products` rows, then best-effort enrich/validate via the API. Never hard-fail a product when stats are unavailable.

## Files
- `src/affiliate_research.py` (create)

## Requirements
1. `add_products(raw: str) -> dict` — split textarea on newlines, `digistore24.parse_product_id` each, upsert into `affiliate_products` (INSERT … ON CONFLICT(product_id) preserve status). Return `{"added": n, "skipped_existing": n, "invalid": n}`.
2. `validate_and_enrich() -> None` — for each `status='candidate'` product:
   - Try `digistore24.get_marketplace_entry(entry_id or product_id)`.
   - If resolved: set commission_pct=`affiliate_share`, epc=`stats_affiliate_profit_visitor`, cancel_rate=`stats_cancel_rate`, conversion_rate=`stats_conversion_rate`, stars=`stats_stars`, headline, language, currency, entry_id, `stats_ok=1`, `score = commission_pct * max(epc, 0.01)`, `last_checked=now`.
   - Auto-exclude (status='excluded') when `commission_pct < settings.digistore24_min_commission` OR `cancel_rate > settings.digistore24_max_cancel_rate` OR headline matches `offers._BLOCKED_PATTERNS`.
   - If unresolved: leave candidate, set `stats_ok=0`, log "stats unavailable for %s — relying on live test". Do not raise.
3. `pick_next_product()` — highest-score `candidate` row (mirror `offers.pick_next_offer`); return a dict/row or None.

## Existing Code to Reference
- `src/offers.py` (`sync_offers`, `pick_next_offer`, `_BLOCKED_PATTERNS`, upsert pattern)
- `src/db.py` (`fetchone`, `fetchall`, `execute`)

## Acceptance Criteria
- [ ] `add_products("567890\n\nhttps://www.digistore24.com/redir/111/x/\ngarbage")` returns counts and inserts 2 rows
- [ ] `validate_and_enrich()` runs without raising when entries don't resolve (stats_ok stays 0, status stays candidate)
- [ ] Re-adding an existing product does not reset its status

## Dependencies
- Task 001, 003

## Commit Message
feat: affiliate product intake, validation and enrichment
