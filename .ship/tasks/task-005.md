# Task 005: Promotion page template

## Type
ui

## Description
Light-theme promotion/review page template, visually distinct from the dark bridge landers. Follows `.ship/design-notes.md`.

## Files
- `src/templates/affiliate_review.html` (create)

## Requirements
1. Light theme, white background, single centered column max 720px, fully mobile responsive (inline `<style>`, no build step — match how existing templates are self-contained).
2. Sections rendered from context vars: affiliate disclosure bar (top), h1, Quick Verdict card (star rating 1–5 + numeric score + 2-sentence summary + CTA button), what_is, how_it_works, benefits, pros/cons two-column grid, who_for, pricing, verdict, FAQ (loop), footer with disclosure.
3. CTA button href = `/aff/{{ slug }}`.
4. `<head>`: `<title>`, meta description, canonical, `robots: index,follow`, Schema.org Review + FAQPage JSON-LD built from the same vars.
5. Use Jinja2 (matches `Jinja2Templates`). Guard optional lists with `{% if %}`.

## Existing Code to Reference
- `src/templates/lander_base.html` (self-contained template style)
- `.ship/design-notes.md` and `.ship/design-refs/` (layout/tokens)

## Acceptance Criteria
- [ ] Template renders with a sample context without Jinja errors
- [ ] Star rating, pros/cons grid, FAQ, disclosure bar all present
- [ ] Valid Review + FAQPage JSON-LD in head

## Dependencies
- Task 001

## Commit Message
feat: add affiliate promotion page template
