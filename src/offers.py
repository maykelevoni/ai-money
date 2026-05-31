"""Offer sync, clean-vertical filtering, and candidate selection."""
from __future__ import annotations

import logging
import os
from typing import Optional

from src import db
from src.clients import cpa as cpa_client
from src.clients.cpa import OfferRecord
from src.models import Offer

logger = logging.getLogger(__name__)

# Substrings that must appear in the normalized vertical field for an offer to be
# considered clean. Match is case-insensitive substring on offer.vertical.
_ALLOWED_VERTICAL_PATTERNS: tuple[str, ...] = (
    "free trial",
    "free-trial",
    "freetrial",
    "lead gen",
    "lead-gen",
    "leadgen",
    "lead generation",
    "email submit",
    "email-submit",
    "emailsubmit",
    "zip submit",
    "zip-submit",
    "zipsubmit",
    "app install",
    "app-install",
    "appinstall",
    "cpi",          # cost-per-install
)

# Any match anywhere in the offer name OR vertical → offer is excluded.
_BLOCKED_PATTERNS: tuple[str, ...] = (
    # Sweepstakes / prize-bait
    "sweepstake",
    "you won",
    "you have won",
    "lottery",
    # Content-locking
    "content lock",
    "content-lock",
    "contentlock",
    " locker",      # space-prefix avoids "blocker" false-positives
    # Adult / grey-area
    "adult",
    " xxx",
    "porn",
    "dating",
    # Sketchy financial / gambling
    "casino",
    "gambling",
    "forex",
    "crypto",
    "binary option",
)

# Cheap push/pop GEOs: tier-1 for payout, tier-2 for high volume + low CPM.
CHEAP_TRAFFIC_GEOS: frozenset[str] = frozenset({
    # Tier 1
    "US", "CA", "AU", "GB", "NZ",
    # Western Europe
    "DE", "FR", "IT", "ES",
    # Eastern Europe
    "PL", "RO", "UA", "CZ", "HU", "BG",
    # Asia-Pacific
    "IN", "PH", "ID", "TH", "VN", "MY", "SG",
    # LatAm
    "MX", "BR", "CO", "AR", "CL",
    # Africa
    "ZA", "NG", "KE", "EG",
})

_MIN_PAYOUT: float = float(os.getenv("MIN_OFFER_PAYOUT", "0.50"))


def _is_clean(offer: OfferRecord) -> bool:
    """Return True only if the offer is in an explicitly allowed clean vertical."""
    combined = (offer.name + " " + offer.vertical).lower()

    for pattern in _BLOCKED_PATTERNS:
        if pattern in combined:
            logger.debug("Blocked offer %r: matched blocked pattern %r", offer.offer_id, pattern)
            return False

    vertical_lower = offer.vertical.lower()
    for pattern in _ALLOWED_VERTICAL_PATTERNS:
        if pattern in vertical_lower:
            return True

    logger.debug(
        "Offer %r has unrecognized vertical %r — excluded (not in allow-list)",
        offer.offer_id, offer.vertical,
    )
    return False


def _geo_ok(offer: OfferRecord) -> bool:
    """Return True if the offer allows at least one cheap-traffic GEO, or has no GEO restriction."""
    if not offer.geo:
        return True
    geos = {g.strip().upper() for g in offer.geo}
    return bool(geos & CHEAP_TRAFFIC_GEOS)


def sync_offers() -> tuple[int, int]:
    """Fetch offers from all configured CPA networks, filter to clean verticals, and upsert.

    New offers are inserted with status 'candidate'. Existing offers have their metadata
    refreshed but their status is preserved (a loser stays a loser).

    Returns:
        (inserted, updated) counts.
    """
    raw_offers = cpa_client.list_offers()
    inserted = 0
    updated = 0

    for offer in raw_offers:
        if offer.payout < _MIN_PAYOUT:
            continue
        if not _is_clean(offer):
            continue
        if not _geo_ok(offer):
            continue

        raw_id = offer.offer_id.split(":", 1)[-1]
        geo_str = ",".join(offer.geo)

        existing = db.fetchone(
            "SELECT id FROM offers WHERE network = ? AND network_offer_id = ?",
            (offer.network, raw_id),
        )
        if existing:
            db.execute(
                """UPDATE offers
                      SET name = ?, vertical = ?, payout = ?, geo = ?, tracking_url = ?
                    WHERE id = ?""",
                (offer.name, offer.vertical, offer.payout, geo_str,
                 offer.tracking_url_template, existing["id"]),
            )
            updated += 1
        else:
            db.execute(
                """INSERT INTO offers
                       (network, network_offer_id, name, vertical, payout, geo, status, tracking_url)
                   VALUES (?, ?, ?, ?, ?, ?, 'candidate', ?)""",
                (offer.network, raw_id, offer.name, offer.vertical,
                 offer.payout, geo_str, offer.tracking_url_template),
            )
            inserted += 1

    logger.info("sync_offers: %d inserted, %d updated (from %d raw)", inserted, updated, len(raw_offers))
    return inserted, updated


def pick_next_offer() -> Optional[Offer]:
    """Return the highest-payout candidate offer.

    Skips offers with status 'loser' or 'excluded'. Returns None when no
    candidates remain.
    """
    row = db.fetchone(
        "SELECT * FROM offers WHERE status = 'candidate' ORDER BY payout DESC LIMIT 1"
    )
    if row is None:
        return None
    return _row_to_offer(row)


def mark_offer(offer_id: int, status: str) -> None:
    """Set the status of an offer. Valid: candidate|testing|winner|loser|excluded."""
    db.execute("UPDATE offers SET status = ? WHERE id = ?", (status, offer_id))


def _row_to_offer(row) -> Offer:
    return Offer(
        id=row["id"],
        network=row["network"],
        network_offer_id=row["network_offer_id"],
        name=row["name"],
        vertical=row["vertical"],
        payout=float(row["payout"]),
        geo=row["geo"],
        status=row["status"],
        tracking_url=row["tracking_url"],
        first_seen=row["first_seen"],
        last_tested=row["last_tested"],
    )
