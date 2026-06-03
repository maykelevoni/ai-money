# Task 001: Database tables for affiliate products & pages

## Description
Add the two SQLite tables that back the Digistore24 affiliate track. `init_db()` already executes `schema.sql` idempotently on boot, so no migration code is needed.

## Files
- `src/schema.sql` (modify — append)

## Requirements
1. Add `affiliate_products` table exactly per `.ship/plan.md` Section 2 (columns: product_id UNIQUE, entry_id, headline, language, currency, commission_pct, epc, cancel_rate, conversion_rate, stars, score, stats_ok, status CHECK candidate/testing/winner/loser/excluded/paused, rules_json, first_seen, last_checked).
2. Add `affiliate_pages` table per plan (product_id FK, slug UNIQUE, title, file_path, views, clicks, status CHECK live/paused, created_at) + `idx_aff_pages_slug`.
3. Use the same formatting/defaults style as existing tables (`datetime('now')`, `CHECK(...)`).

## Existing Code to Reference
- `src/schema.sql` (table style, the existing `offers` table is the closest analog)

## Acceptance Criteria
- [ ] Both tables added with correct columns, constraints, index
- [ ] `python3 -c "import sqlite3; sqlite3.connect(':memory:').executescript(open('src/schema.sql').read())"` runs without error

## Dependencies
- none

## Commit Message
feat: add affiliate_products and affiliate_pages tables
