"""Affiliate product intake, validation, and enrichment (Digistore24)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src import db
from src.clients import digistore24
from src.config import settings
from src.offers import _BLOCKED_PATTERNS

logger = logging.getLogger(__name__)


def add_products(raw: str) -> dict:
    """Parse pasted lines into affiliate_products rows.

    Returns {"added": n, "skipped_existing": n, "invalid": n}.
    Existing rows (by product_id) are not modified — status is preserved.
    """
    added = 0
    skipped_existing = 0
    invalid = 0

    for line in raw.splitlines():
        product_id = digistore24.parse_product_id(line)
        if product_id is None:
            if line.strip():
                invalid += 1
            continue

        existing = db.fetchone(
            "SELECT id FROM affiliate_products WHERE product_id = ?",
            (product_id,),
        )
        if existing:
            skipped_existing += 1
            continue

        db.execute(
            "INSERT INTO affiliate_products (product_id, status) VALUES (?, 'candidate')",
            (product_id,),
        )
        added += 1

    logger.info(
        "add_products: %d added, %d skipped_existing, %d invalid",
        added, skipped_existing, invalid,
    )
    return {"added": added, "skipped_existing": skipped_existing, "invalid": invalid}


def validate_and_enrich() -> None:
    """Enrich candidate products via getMarketplaceEntry (best-effort).

    Never raises. Products that can't be resolved stay as candidates with stats_ok=0.
    Products failing commission/cancel-rate thresholds or blocked patterns are excluded.
    """
    candidates = db.fetchall(
        "SELECT * FROM affiliate_products WHERE status = 'candidate'"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for row in candidates:
        product_id = row["product_id"]
        lookup_id = row["entry_id"] or product_id

        try:
            entry = digistore24.get_marketplace_entry(lookup_id)
        except Exception:
            entry = None

        if entry is None:
            logger.info("stats unavailable for %s — relying on live test", product_id)
            db.execute(
                "UPDATE affiliate_products SET stats_ok = 0, last_checked = ? WHERE product_id = ?",
                (now, product_id),
            )
            continue

        commission_pct = float(entry.get("affiliate_share") or 0.0)
        epc = float(entry.get("stats_affiliate_profit_visitor") or 0.0)
        cancel_rate = float(entry.get("stats_cancel_rate") or 0.0)
        conversion_rate = float(entry.get("stats_conversion_rate") or 0.0)
        stars = float(entry.get("stats_stars") or 0.0)
        headline = entry.get("headline") or ""
        language = entry.get("language") or ""
        currency = entry.get("currency") or ""
        resolved_entry_id = entry.get("entry_id") or lookup_id
        score = commission_pct * max(epc, 0.01)

        db.execute(
            """UPDATE affiliate_products
                  SET commission_pct = ?, epc = ?, cancel_rate = ?, conversion_rate = ?,
                      stars = ?, headline = ?, language = ?, currency = ?,
                      entry_id = ?, stats_ok = 1, score = ?, last_checked = ?
                WHERE product_id = ?""",
            (commission_pct, epc, cancel_rate, conversion_rate,
             stars, headline, language, currency,
             resolved_entry_id, score, now, product_id),
        )

        exclude_reason = _check_exclusion(commission_pct, cancel_rate, headline)
        if exclude_reason:
            db.execute(
                "UPDATE affiliate_products SET status = 'excluded' WHERE product_id = ?",
                (product_id,),
            )
            logger.info("excluded %s: %s", product_id, exclude_reason)
        else:
            logger.info(
                "enriched %s: commission=%.1f%% epc=%.3f cancel=%.1f%% score=%.4f",
                product_id, commission_pct, epc, cancel_rate, score,
            )


def _check_exclusion(commission_pct: float, cancel_rate: float, headline: str) -> str | None:
    if commission_pct < settings.digistore24_min_commission:
        return f"commission {commission_pct:.1f}% < min {settings.digistore24_min_commission:.1f}%"
    if cancel_rate > settings.digistore24_max_cancel_rate:
        return f"cancel rate {cancel_rate:.1f}% > max {settings.digistore24_max_cancel_rate:.1f}%"
    headline_lower = headline.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in headline_lower:
            return f"blocked pattern {pattern!r} in headline"
    return None


def pick_next_product() -> Optional[dict]:
    """Return the highest-score candidate product row, or None."""
    row = db.fetchone(
        "SELECT * FROM affiliate_products WHERE status = 'candidate' ORDER BY score DESC LIMIT 1"
    )
    if row is None:
        return None
    return dict(row)
