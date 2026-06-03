# Task 003: Digistore24 API client

## Description
Thin, typed client for the verified Digistore24 classic API. No business logic.

## Files
- `src/clients/digistore24.py` (create)

## Requirements
1. `BASE = "https://www.digistore24.com/api/call"`; header `X-DS-API-KEY: settings.digistore24_api_key`, `Accept: application/json`. Reuse httpx + a `_retry` like `cpa.py`.
2. `parse_product_id(line: str) -> str | None` — accept a bare numeric id; extract the id from a `…/redir/{id}/…` link or any URL path segment that is the Digistore24 numeric product id. Return None for blank/invalid.
3. `get_user_info() -> dict` — GET `getUserInfo`; return `data`. Used to auto-resolve affiliate name (`user_name`).
4. `resolve_affiliate_name() -> str` — return `settings.digistore24_affiliate_name` or fall back to `get_user_info()["user_name"]`.
5. `get_marketplace_entry(entry_id: str) -> dict | None` — GET `getMarketplaceEntry?entry_id=...`; return `data` dict on success, **None** when result is not success / object not found / 403 (best-effort, never raise for missing).
6. `build_promolink(product_id, affiliate_name, campaign_key="") -> str` → `https://www.digistore24.com/redir/{product_id}/{affiliate_name}/{campaign_key}` (omit trailing slash/segment cleanly when campaign_key empty).
7. Typed errors `Digistore24Error`, `Digistore24AuthError` for genuine failures (401).

## Existing Code to Reference
- `src/clients/cpa.py` (httpx client, `_retry`, typed errors, normalize pattern)
- `spike/check_digistore24.py` (verified call shape, field names)
- `.ship/learnings.md` (Digistore24 VERIFIED LIVE section)

## Acceptance Criteria
- [ ] `parse_product_id` handles: "567890", "https://www.digistore24.com/redir/567890/paidrew/", a marketplace URL
- [ ] `build_promolink("567890","paidrew","my-slug")` == `https://www.digistore24.com/redir/567890/paidrew/my-slug`
- [ ] `get_marketplace_entry("999999999")` returns None (not found) without raising
- [ ] `get_user_info()` returns a dict with `user_name` when key is set (skip if no key)

## Dependencies
- Task 002

## Commit Message
feat: add Digistore24 API client (promolink, marketplace entry, parsing)
