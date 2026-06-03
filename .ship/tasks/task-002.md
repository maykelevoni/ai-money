# Task 002: Config keys & readiness for Digistore24

## Description
Expose Digistore24 settings through the existing DB→env→default resolver and the dashboard-managed settings list.

## Files
- `src/config.py` (modify)

## Requirements
1. Add `_LiveSettings` properties: `digistore24_api_key` (resolve `DIGISTORE24_API_KEY`, fall back to existing `DIGISTORE` env var), `digistore24_affiliate_name` (resolve `DIGISTORE24_AFFILIATE_NAME`, default ""), `digistore24_min_commission` (float, default 50.0), `digistore24_max_cancel_rate` (float, default 15.0).
2. Add to `MANAGED_SETTINGS`: `DIGISTORE24_API_KEY` (password/secret), `DIGISTORE24_AFFILIATE_NAME` (text), `DIGISTORE24_MIN_COMMISSION` (number), `DIGISTORE24_MAX_CANCEL_RATE` (number).
3. Add `has_digistore() -> bool` returning `bool(settings.digistore24_api_key)`.
4. Do NOT change existing engine-readiness for the CPA engine; the affiliate track gates independently on `has_digistore()`.

## Existing Code to Reference
- `src/config.py` — `_resolve`, `_resolve_float`, the existing properties, `MANAGED_SETTINGS`, `has_cpa()`

## Acceptance Criteria
- [ ] `from src.config import settings; settings.digistore24_api_key` returns the `DIGISTORE` value already in `config/.env`
- [ ] `config.has_digistore()` is True with that key present
- [ ] New rows appear on the dashboard Settings page

## Dependencies
- none

## Commit Message
feat: add Digistore24 config keys and readiness check
