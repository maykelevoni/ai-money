# Task 008: Landing page + ad creative generation

## Type
ui

## Description
LLM generates a fast, mobile-first pre-lander (bridge page) for an offer plus push ad creatives (title/description/icon). The lander warms the click before sending it to the CPA offer. (Plan Sections 4, 5.)

## Files
- `src/generate.py` (create)
- `src/templates/lander_base.html` (create)

## Requirements
1. `generate_lander(offer) -> path`: LLM writes angle + headline + body copy for the offer's vertical; render into `lander_base.html`; write static file to `landers/{slug}.html`. CTA links to `/go/{click_id}` (click_id injected at serve time via template placeholder).
2. `generate_creatives(offer) -> list`: LLM produces N push creatives — title ≤ ~30 chars, description ≤ ~45 chars. Persist to `creatives` table (status active).
3. Icon image (MVP): generate a simple icon with Pillow (text/initial on a colored circle) saved to `static/icons/`. Good enough for MVP; real images later.
4. Lander must be mobile-first, single-column, fast (no heavy assets), with one clear CTA button.

## Existing Code to Reference
- `src/clients/llm.py` (Task 006), `src/db.py`, `src/models.py`.
- `.ship/plan.md` Section 4 (mobile-first, fast-loading rationale).

## Acceptance Criteria
- [ ] `generate_lander(offer)` writes a valid mobile-first HTML file with a CTA to `/go/...`.
- [ ] `generate_creatives(offer)` returns creatives within push char limits, persisted.
- [ ] An icon image is produced per creative/campaign.

## Dependencies
- Task 006, Task 007, Task 003

## Commit Message
feat: AI landing page + push creative generation
