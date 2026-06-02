# Task 003: Database layer

## Description
SQLite schema + thin data-access layer. All 8 tables from the plan, auto-created on startup. (Plan Section 2.)

## Files
- `src/schema.sql` (create)
- `src/db.py` (create)
- `src/models.py` (create)

## Requirements
1. `schema.sql`: tables offers, campaigns, creatives, clicks, conversions, spend_snapshots, decisions, budget_ledger — exact columns per Plan Section 2. Add helpful indexes (clicks.click_id, conversions.click_id, spend_snapshots.campaign_id).
2. `db.py`: connection helper (single SQLite file at `data/engine.db`), `init_db()` that runs schema.sql if tables absent, and small query helpers (execute, fetchone, fetchall). Enable WAL mode + foreign keys.
3. `models.py`: lightweight dataclasses mirroring each table row for typed passing between modules.
4. `main.py` startup calls `init_db()`.

## Existing Code to Reference
- `.ship/plan.md` Section 2 (exact columns + status enums).
- `src/main.py`, `src/config.py` (Task 002).

## Acceptance Criteria
- [ ] First boot creates `data/engine.db` with all 8 tables.
- [ ] Re-boot is idempotent (no error if tables exist).
- [ ] Dataclasses exist for every table.

## Dependencies
- Task 002

## Commit Message
feat: SQLite schema, db helpers, and row models
