# Task 007: Public page serving & click-tracking routes

## Description
Serve generated pages and redirect clicks through the promolink with tracking.

## Files
- `src/affiliate_routes.py` (create)
- `src/main.py` (modify — register)

## Requirements
1. `register_affiliate_routes(app)`:
   - `GET /p/{slug}` → read `affiliate_pages` by slug; if missing or status='paused' → 404; else `UPDATE … views = views + 1`, return the file's HTML (FileResponse/HTMLResponse).
   - `GET /aff/{slug}` → look up product_id via the page; `UPDATE … clicks = clicks + 1`; build `digistore24.build_promolink(product_id, digistore24.resolve_affiliate_name(), slug)`; 302 redirect. 404 for unknown slug.
2. Register in `main.py` next to the other `register_*` calls.

## Existing Code to Reference
- `src/home.py` (serving static/generated HTML, route registration pattern)
- `src/tracker.py` (click handling / redirect pattern)
- `src/main.py` (register_* wiring)

## Acceptance Criteria
- [ ] `GET /p/unknown` → 404; valid slug → 200 and increments views
- [ ] `GET /aff/{slug}` → 302 to a `…/redir/{id}/{aff}/{slug}` URL and increments clicks
- [ ] App still boots via TestClient

## Dependencies
- Task 003, 006

## Commit Message
feat: serve affiliate pages and track click-throughs
