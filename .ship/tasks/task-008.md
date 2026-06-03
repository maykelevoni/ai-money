# Task 008: Dashboard "Products to promote" panel + explainer

## Type
ui

## Description
Operator-facing panel to paste product links/IDs, with a self-serve inline explainer, plus a live status list. This is the only manual step in the whole track.

## Files
- `src/dashboard.py` (modify — add authed GET data + `POST /dashboard/products`)
- `src/templates/dashboard.html` (modify — add panel)

## Requirements
1. `POST /dashboard/products` (authed like other dashboard routes): read `products` form field, call `affiliate_research.add_products(...)`, redirect back to `/dashboard` with a saved flag.
2. Dashboard data: add an `affiliate_products` list (id, product_id, headline, commission_pct, cancel_rate, status, stats_ok, page slug+status) to the dashboard context.
3. `dashboard.html` panel "Products to promote":
   - `<textarea name="products">` (one link/ID per line) + Save button posting to `/dashboard/products`.
   - **Collapsible inline explainer** (`<details>`): steps (open Digistore24 marketplace → pick by rules → copy product link → paste here) + cheat-sheet (commission 50%+, low cancel rate, auto-approve only, $30–90, avoid grey/scam niches). Same content as `HOW-TO-PICK-PRODUCTS.md`.
   - Live table of products with status badges; show a "stats unavailable — judged by live test" tag when `stats_ok=0`.
4. Match the existing dark dashboard styling.

## Existing Code to Reference
- `src/dashboard.py` (`register_dashboard_routes`, auth via `_is_authed`, settings POST pattern)
- `src/templates/dashboard.html` (section/card styling)
- `HOW-TO-PICK-PRODUCTS.md` (explainer copy)

## Acceptance Criteria
- [ ] Pasting IDs/links and clicking Save inserts products and they appear in the list
- [ ] Explainer is visible/collapsible with the pick rules
- [ ] Unauthed POST is rejected like other dashboard routes

## Dependencies
- Task 004

## Commit Message
feat: dashboard product intake panel with pick-guide explainer
