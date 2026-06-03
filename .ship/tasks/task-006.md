# Task 006: LLM page generation

## Description
Generate a promotion page per product via the LLM and persist it.

## Files
- `src/affiliate_generate.py` (create)

## Requirements
1. `generate_page(product_row) -> str` (returns slug): prompt the LLM (via `src/clients/llm.py`, model `settings.llm_model`) to return JSON with: title, meta_desc, h1, what_is, how_it_works, benefits (list), pros (list), cons (list), who_for, pricing, verdict, rating (1-5 float), summary, faq (list of {q,a}). Feed it the product headline/description/commission from the row.
2. Render `affiliate_review.html` with those vars + slug; write to `pages/{slug}.html` (create `pages/` if missing). Slug = kebab-case of headline, deduped against `affiliate_pages.slug`.
3. Insert a row into `affiliate_pages` (product_id, slug, title, file_path, status='live').
4. `generate_pending(limit: int) -> int` — generate pages for candidate products that have no page yet, up to `limit`; return count. Respect LLM budget (small limit).
5. Tolerate malformed LLM JSON (retry once, then skip with a logged warning).

## Existing Code to Reference
- `src/generate.py` (LLM call pattern, JSON parsing, file writing for landers)
- `src/clients/llm.py` (client interface)

## Acceptance Criteria
- [ ] `generate_page` writes `pages/{slug}.html` and inserts an `affiliate_pages` row
- [ ] Slug collisions get a numeric suffix
- [ ] Malformed JSON does not crash the job

## Dependencies
- Task 001, 005

## Commit Message
feat: LLM generation of affiliate promotion pages
