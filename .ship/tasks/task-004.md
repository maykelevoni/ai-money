# Task 004: Budget ledger + cap enforcement

## Description
The single chokepoint for all spend. Every money-moving action asks this module "am I allowed?" — this is how "can never spend more than funded" becomes real. Built early because launch/optimize depend on it. (Plan Sections 1, 6.1.)

## Files
- `src/budget.py` (create)
- `tests/test_budget.py` (create)

## Requirements
1. `record_deposit(amount)` and `record_spend(amount)` write `budget_ledger` rows with a running total.
2. `remaining_global()` and `spent_today()` computed from the ledger.
3. `can_spend(amount) -> bool`: false if it would exceed GLOBAL_BUDGET or DAILY_CAP.
4. `is_global_exhausted()` / `is_daily_exhausted()` helpers for the budget-guard job.
5. Pure logic, no external API calls — operates only on the ledger/db.

## Existing Code to Reference
- `src/db.py`, `src/models.py` (Task 003).
- `src/config.py` for GLOBAL_BUDGET / DAILY_CAP (Task 002).

## Acceptance Criteria
- [ ] Test: spend cannot push running total above GLOBAL_BUDGET.
- [ ] Test: daily spend cannot exceed DAILY_CAP; resets next day.
- [ ] Test: remaining/spent_today compute correctly across mixed deposit/spend rows.

## Dependencies
- Task 003

## Commit Message
feat: budget ledger with global + daily cap enforcement
