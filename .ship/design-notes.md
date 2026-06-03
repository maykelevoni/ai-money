# Design Notes: Affiliate Review Pages

## Page Composition (section order)
1. **Disclosure bar** — thin top bar: "This page contains affiliate links. We may earn a commission."
2. **Header** — product name as H1, star rating (X.X/5), one-line verdict
3. **Hero image** — product/niche image, full-width, max 400px tall
4. **Quick Verdict box** — highlighted card: rating, 2-sentence summary, primary CTA button
5. **What is [Product]?** — H2, 2-3 paragraphs
6. **How Does It Work?** — H2, 2-3 paragraphs
7. **Key Benefits** — H2, bulleted list (5-7 items with checkmarks)
8. **Pros & Cons** — H2, two-column grid (green ✓ pros / red ✗ cons)
9. **Who Is It For?** — H2, 2 paragraphs
10. **Pricing** — H2, price + what you get + money-back guarantee
11. **Final Verdict** — H2, rating repeated, 2-3 sentences, secondary CTA
12. **FAQ** — H2, 3-5 Q&A pairs (schema.org FAQPage markup)
13. **Footer** — disclosure + copyright

## CTA Design
- Primary CTA: large button, full-width on mobile, prominent color
- Text pattern: "Get [Product Name] →" or "Visit Official Site →"
- Placed: Quick Verdict box + after Final Verdict
- Click tracked via `/aff/{slug}` → redirects to affiliate link

## Rating Display
- Stars out of 5 (filled/empty)
- Numeric label (e.g., "4.2 / 5")
- Category sub-ratings optional (effectiveness, value, ease of use)

## Trust Signals
- "Expert Review" badge in header
- Money-back guarantee mention in pricing section
- Affiliate disclosure (top bar + footer)
- "Last updated: [date]" in header byline

## Visual Style
- Light theme (white/off-white background) — opposite of the dark bridge landers
- Clean sans-serif (Inter or system-ui)
- Max width 720px centered — readable column
- Accent color: green (#16A34A) for pros/CTAs
- Danger color: red (#DC2626) for cons
- Neutral: slate gray for body text
- Schema.org: Review + FAQPage markup in <head>

## Mobile
- Single column at all breakpoints
- CTA buttons min 52px height
- Font size ≥ 16px for body
- Hero image height capped at 240px on mobile

## SEO Structure
- `<title>`: "[Product] Review [Year]: Does It Really Work?"
- `<meta description>`: 140-155 chars, includes product name + benefit + CTA hint
- `<h1>`: matches title intent
- `<h2>` per major section
- `canonical` URL pointing to `/p/{slug}`
- `robots`: index,follow (opposite of bridge landers which are noindex)
- Schema.org: Review type with ratingValue, author, itemReviewed
