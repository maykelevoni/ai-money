"""Generate affiliate promotion pages via LLM and persist them.

Mirrors generate.py's LLM call pattern. Pages are written to pages/{slug}.html
and indexed in the affiliate_pages table.
"""
from __future__ import annotations

import json
import logging
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src import db
from src.clients import llm

_log = logging.getLogger(__name__)

_PAGES_DIR = Path("pages")
_TEMPLATE_DIR = Path(__file__).parent / "templates"

_SYSTEM = textwrap.dedent("""\
    You are a professional affiliate product reviewer. Write honest, balanced,
    benefit-focused copy for a review page. No fake scarcity, no deceptive claims.
    Output ONLY the exact JSON requested — no markdown fences, no extra text.
""")


def _make_slug(headline: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", headline.lower()).strip("-")


def _dedup_slug(base: str) -> str:
    """Return base slug if unused, otherwise append incrementing suffix."""
    row = db.fetchone("SELECT 1 FROM affiliate_pages WHERE slug = ?", (base,))
    if not row:
        return base
    i = 2
    while True:
        candidate = f"{base}-{i}"
        row = db.fetchone("SELECT 1 FROM affiliate_pages WHERE slug = ?", (candidate,))
        if not row:
            return candidate
        i += 1


def _call_llm(prompt: str) -> dict:
    """Call LLM and parse JSON. Raises ValueError on parse failure."""
    raw = llm.complete(_SYSTEM, prompt, max_tokens=1800)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"LLM returned no JSON object: {raw[:300]}")
    return json.loads(match.group())


def generate_page(product_row) -> str:
    """Generate a promotion page for the given product row.

    Returns the slug of the written page.
    Retries LLM once on malformed JSON; skips with a warning on second failure.
    """
    _PAGES_DIR.mkdir(parents=True, exist_ok=True)

    headline = product_row["headline"] or product_row["product_id"]
    product_id = product_row["product_id"]
    commission = product_row["commission_pct"]

    prompt = textwrap.dedent(f"""\
        Product name: {headline}
        Commission rate: {commission}%
        Digistore24 product ID: {product_id}

        Write a comprehensive affiliate review page for this product.
        Return a single JSON object — no markdown, no extra text:
        {{
            "title": "<SEO page title, 50-60 chars>",
            "meta_desc": "<meta description, 140-160 chars>",
            "h1": "<H1 headline for the review page>",
            "what_is": "<2-3 sentences: what the product is and who makes it>",
            "how_it_works": "<2-3 sentences: how the product works step-by-step>",
            "benefits": ["<benefit 1>", "<benefit 2>", "<benefit 3>", "<benefit 4>"],
            "pros": ["<pro 1>", "<pro 2>", "<pro 3>"],
            "cons": ["<con 1>", "<con 2>"],
            "who_for": "<1-2 sentences: ideal customer profile>",
            "pricing": "<pricing details and value summary>",
            "verdict": "<2-3 sentence honest verdict>",
            "rating": <float 1.0–5.0 based on honest assessment>,
            "summary": "<1 sentence executive summary>",
            "faq": [
                {{"q": "<question 1>", "a": "<answer 1>"}},
                {{"q": "<question 2>", "a": "<answer 2>"}},
                {{"q": "<question 3>", "a": "<answer 3>"}}
            ]
        }}
    """)

    data: dict | None = None
    for attempt in (1, 2):
        try:
            data = _call_llm(prompt)
            break
        except (ValueError, json.JSONDecodeError) as exc:
            if attempt == 1:
                _log.warning("LLM JSON parse failed (attempt 1) for %s — retrying: %s", product_id, exc)
            else:
                _log.warning("LLM JSON parse failed (attempt 2) for %s — skipping: %s", product_id, exc)
                return ""

    if not data:
        return ""

    # Ensure list fields are actually lists
    for field in ("benefits", "pros", "cons", "faq"):
        if not isinstance(data.get(field), list):
            data[field] = []

    # Clamp rating to [1.0, 5.0]
    try:
        data["rating"] = max(1.0, min(5.0, float(data.get("rating", 3.0))))
    except (TypeError, ValueError):
        data["rating"] = 3.0

    slug_base = _make_slug(headline)
    slug = _dedup_slug(slug_base)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("affiliate_review.html")
    html = tmpl.render(slug=slug, created_at=created_at, **data)

    out_path = _PAGES_DIR / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")

    db.execute(
        """INSERT INTO affiliate_pages (product_id, slug, title, file_path, status)
           VALUES (?, ?, ?, ?, 'live')""",
        (product_id, slug, data.get("title", headline), str(out_path)),
    )

    _log.info("Generated affiliate page: %s -> %s", product_id, out_path)
    return slug


def generate_pending(limit: int = 5) -> int:
    """Generate pages for candidate products that have no page yet.

    Returns the count of pages successfully generated.
    Caps at `limit` to respect LLM budget.
    """
    rows = db.fetchall(
        """SELECT ap.*
           FROM affiliate_products ap
           LEFT JOIN affiliate_pages pg ON pg.product_id = ap.product_id
           WHERE ap.status = 'candidate'
             AND pg.id IS NULL
           ORDER BY ap.score DESC, ap.first_seen ASC
           LIMIT ?""",
        (limit,),
    )

    count = 0
    for row in rows:
        slug = generate_page(row)
        if slug:
            count += 1

    return count
