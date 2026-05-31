"""Generate AI landing pages and push ad creatives for CPA offers.

Landing pages are static HTML pre-landers that warm up cold push traffic.
Each generated lander uses a CLICK_ID placeholder in the CTA href which
tracker.py replaces at serve time with the real click UUID.
"""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageDraw, ImageFont

from src import db
from src.clients import llm
from src.models import Creative, Offer

_LANDER_DIR = Path("landers")
_ICON_DIR = Path("static/icons")
_TEMPLATE_DIR = Path(__file__).parent / "templates"

# Unsplash photo IDs matched to offer verticals (from design-ref skill)
_VERTICAL_IMAGES: dict[str, str] = {
    "health":     "1545205597",
    "wellness":   "1571019613",
    "fitness":    "1506126613",
    "finance":    "1460925895917",
    "fintech":    "1521737604",
    "dating":     "1544161515",
    "lifestyle":  "1545205597",
    "gaming":     "1633356122",
    "software":   "1714698628",
    "tech":       "1714698628",
    "education":  "1605379399",
    "insurance":  "1521737604",
}
_DEFAULT_IMAGE = "1518770660"

_SYSTEM = textwrap.dedent("""\
    You are a performance-marketing copywriter specializing in CPA affiliate offers.
    Write punchy, benefit-driven, honest copy for mobile pre-landers and push ads.
    No fake prizes, no deceptive "you won" claims, no misleading urgency.
    Focus on legitimate benefits, curiosity, and social proof.
    Output ONLY the exact JSON requested — no markdown fences, no extra text.
""")


def _slug(offer: Offer) -> str:
    safe = re.sub(r"[^a-z0-9]+", "-", offer.name.lower()).strip("-")
    return f"{safe}-{offer.id}"


def _image_url_for_vertical(vertical: str) -> str:
    key = vertical.lower().split("/")[0].strip().split()[0]
    photo_id = _VERTICAL_IMAGES.get(key, _DEFAULT_IMAGE)
    return f"https://images.unsplash.com/photo-{photo_id}?w=800&q=75&auto=format&fit=crop"


def generate_lander(offer: Offer) -> str:
    """LLM writes copy for the offer; renders into lander_base.html; saves to landers/{slug}.html.

    Returns the relative path to the generated file.
    The CTA button links to /go/CLICK_ID — tracker.py replaces CLICK_ID at serve time.
    """
    _LANDER_DIR.mkdir(parents=True, exist_ok=True)

    prompt = textwrap.dedent(f"""\
        Offer name: {offer.name}
        Vertical: {offer.vertical}
        Conversion action: free signup / trial / install (no purchase required)
        GEO: {offer.geo}

        Write copy for a mobile bridge pre-lander that warms up a cold push-traffic visitor.
        Return a single JSON object — no markdown, no extra text:
        {{
            "headline": "<6-10 words, punchy benefit>",
            "subheadline": "<1 sentence expanding the promise>",
            "body": "<2-3 short sentences, social proof or key benefits>",
            "benefits": ["<benefit 1>", "<benefit 2>", "<benefit 3>"],
            "cta_text": "<3-6 words starting with an action verb>",
            "badge_text": "<short trust line, e.g. Free · No Credit Card>",
            "above_fold_stat": "<a credibility number, e.g. 2M+ users worldwide>",
            "urgency_line": "<1 short, honest urgency or limited-time line>"
        }}
    """)

    raw = llm.complete(_SYSTEM, prompt, max_tokens=600)

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"LLM returned no JSON object for lander copy: {raw[:300]}")
    data = json.loads(match.group())

    # Ensure benefits is a list; fall back to generic if LLM omitted it
    if not isinstance(data.get("benefits"), list) or not data["benefits"]:
        data["benefits"] = [
            "Quick to complete — under 2 minutes",
            "Free to start — no credit card needed",
            "Trusted by thousands of users",
        ]

    image_url = _image_url_for_vertical(offer.vertical)

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("lander_base.html")
    html = tmpl.render(offer=offer, image_url=image_url, **data)

    slug = _slug(offer)
    out_path = _LANDER_DIR / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)


def generate_creatives(offer: Offer, campaign_id: int, n: int = 3) -> list[Creative]:
    """LLM generates N push notification creatives for the offer.

    Persists each creative to the DB (status=active) and returns the Creative list.
    Title ≤ 30 chars, description ≤ 45 chars — enforced on the LLM output.
    An icon image is generated per creative via Pillow.
    """
    prompt = textwrap.dedent(f"""\
        Offer name: {offer.name}
        Vertical: {offer.vertical}
        GEO: {offer.geo}
        Payout event: free signup / trial / install

        Generate exactly {n} push notification ad creatives.
        Rules:
        - title: ≤ 30 characters (strict)
        - description: ≤ 45 characters (strict)
        - Honest benefit copy — no fake prizes, no deceptive claims
        - Varied angles across the {n} creatives

        Return a JSON array — no markdown, no extra text:
        [
            {{"title": "...", "description": "..."}},
            ...
        ]
    """)

    raw = llm.complete(_SYSTEM, prompt, max_tokens=400)

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"LLM returned no JSON array for creatives: {raw[:300]}")
    items: list[dict] = json.loads(match.group())

    icon_path = _make_icon(offer)

    creatives: list[Creative] = []
    for item in items[:n]:
        title = item.get("title", "")[:30]
        desc = item.get("description", "")[:45]

        cur = db.execute(
            """INSERT INTO creatives
               (campaign_id, traffic_creative_id, title, description, icon_path, status, clicks, ctr)
               VALUES (?, NULL, ?, ?, ?, 'active', 0, 0.0)""",
            (campaign_id, title, desc, icon_path),
        )
        row = db.fetchone("SELECT * FROM creatives WHERE id = ?", (cur.lastrowid,))
        creatives.append(
            Creative(
                id=row["id"],
                campaign_id=row["campaign_id"],
                traffic_creative_id=row["traffic_creative_id"],
                title=row["title"],
                description=row["description"],
                icon_path=row["icon_path"],
                status=row["status"],
                clicks=row["clicks"],
                ctr=row["ctr"],
            )
        )
    return creatives


def _make_icon(offer: Offer) -> str:
    """Render a colored circle with the offer's initial letter using Pillow.

    Returns the relative path (static/icons/<slug>-icon.png).
    This is the MVP icon; real ad images come in a later iteration.
    """
    _ICON_DIR.mkdir(parents=True, exist_ok=True)

    # Palette keyed by vertical — same as the design-ref vertical colors
    _PALETTE: dict[str, str] = {
        "health":    "#2D6A4F",
        "wellness":  "#2D6A4F",
        "fitness":   "#2D6A4F",
        "finance":   "#D4AF37",
        "fintech":   "#D4AF37",
        "dating":    "#FF3366",
        "lifestyle": "#FF3366",
        "gaming":    "#6366F1",
        "software":  "#3B82F6",
        "tech":      "#3B82F6",
        "education": "#7C3AED",
        "insurance": "#1D4ED8",
    }
    key = offer.vertical.lower().split("/")[0].strip().split()[0]
    bg_hex = _PALETTE.get(key, "#1D4ED8")

    size = 128
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Convert hex color to RGB tuple
    r = int(bg_hex[1:3], 16)
    g = int(bg_hex[3:5], 16)
    b = int(bg_hex[5:7], 16)
    draw.ellipse([0, 0, size - 1, size - 1], fill=(r, g, b, 255))

    letter = offer.name[0].upper() if offer.name else "?"
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    for font_path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ):
        try:
            font = ImageFont.truetype(font_path, 64)
            break
        except (OSError, IOError):
            continue
    else:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), letter, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), letter, fill=(255, 255, 255, 255), font=font)

    slug = _slug(offer)
    filename = f"{slug}-icon.png"
    icon_path = _ICON_DIR / filename
    img.save(str(icon_path), "PNG")
    return f"static/icons/{filename}"
