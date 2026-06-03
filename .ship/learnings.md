# Project Learnings

> Persistent knowledge base. Agents read this before every task and append discoveries.
> This file survives resets — it's project-lifetime knowledge.

## Bugs & Fixes
- `src/config.py` originally called bare `load_dotenv()`, which searches CWD/parents for `.env` — but the project's env lives at `config/.env` (where `.env.example` is and SETUP.md points). Fixed to `load_dotenv(Path(__file__).parent.parent / "config" / ".env")` with fallback. Symptom: "Missing CPA network credentials" even with a filled `config/.env`.
- `src/dashboard.py` used the old `templates.TemplateResponse(name, context)` signature. Installed Starlette requires the new order `TemplateResponse(request, name, context)`. Symptom: `TypeError: unhashable type: 'dict'` on GET /dashboard. Drop the `"request"` key from the context dict and pass `request` positionally first.

## Gotchas
- To run/test locally without `python3-venv`: `pip install --target .venv-libs -r requirements.txt` then `PYTHONPATH=.venv-libs:. python3 ...`. Avoids PEP 668 externally-managed errors.
- Modules import `src.config` at import time, so `config.settings` validation runs on ANY import — a missing required env var makes the whole app (and smoke imports) fail fast by design.

## Patterns
- FastAPI app verified via `from fastapi.testclient import TestClient` — boots app, runs DB init, hits endpoints without live external APIs. Good smoke test.
- `spike/check_apis.py` SKIPs (not FAILs) cleanly when keys are absent — safe to run anytime; only does real network checks once keys are set.

## Environment
- Project is NOT a git repo by default — `git init` is needed on first commit.
- `spike/FINDINGS.md` is gitignored (generated output). Only commit the script, not its output.
- System Python is externally-managed (Debian PEP 668). Use `--break-system-packages` for quick installs, or `python3-venv` (need `apt install python3.12-venv`) for proper venvs.

## Digistore24 API — VERIFIED LIVE (2026-06-03, account paidrew / key 1670545)
- Classic API: `GET https://www.digistore24.com/api/call/{function}`, header `X-DS-API-KEY`. JSON `{result, data}`. `ping` + `getUserInfo` work. Account roles: affiliate,merchant; key permission "writable".
- OpenAPI spec: https://www.digistore24.com/api/docs/openapi.yaml (+ ./paths/{fn}.yaml per endpoint). 130+ functions.
- **CRITICAL: NO affiliate product-discovery endpoint exists.** `listMarketplaceEntries` officially = "Lists all marketplace data of THE VENDOR" — i.e. the account's OWN vendor listings, not the public marketplace. Our account has 0 own products → every call returns count=0 regardless of params (verified exhaustively). Same dead-end as ClickBank.
- `listMarketplaceEntries` args: sort_by (1; allowed: name,stars,created,rank,profit,cancel,conversion,revenue), approval_status (4; new/pending/approved/rejected = VENDOR listing status, not affiliate partnership).
- `getMarketplaceEntry(entry_id)` DOES work per-ID and returns rich stats — USABLE for autonomous enrichment once you already have product IDs: affiliate_share (=commission %), stats_affiliate_profit_visitor (=EPC), stats_affiliate_profit_sale, stats_cancel_rate, stats_conversion_rate, stats_stars, stats_seller_rank, price, currency, language, headline, description, main_product_id, all_product_ids, product_category.
- No public unauthenticated marketplace JSON feed found (browse is behind affiliate-dashboard login). So autonomous discovery = scrape (fragile) OR manual ID curation.
- **Implication:** discovery cannot be API-autonomous on Digistore24. Everything DOWNSTREAM of having product IDs (enrichment, ranking, links, pages, traffic) can be. Promolink format still to confirm: /redir/{product_id}/{affiliate}/.
