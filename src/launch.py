"""Launch a budget-capped campaign on PropellerAds for a given CPA offer.

Coordinates: budget check, lander generation, creative generation,
traffic-network campaign creation, and DB persistence.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from src import budget, db
from src.clients import traffic
from src.config import settings
from src.generate import generate_creatives, generate_lander
from src.models import Campaign, Offer

logger = logging.getLogger(__name__)


class BudgetExhaustedError(Exception):
    """Raised when budget guards block a campaign launch."""


def _slug(offer: Offer) -> str:
    safe = re.sub(r"[^a-z0-9]+", "-", offer.name.lower()).strip("-")
    return f"{safe}-{offer.id}"


def _build_tracking_url(slug: str) -> str:
    """Return the lander URL with PropellerAds macro tokens (from spike/FINDINGS.md)."""
    return (
        f"https://{settings.domain}/lp/{slug}"
        "?zone={ZONE_ID}&cost={COST}&country={COUNTRY}&cid={CLICK_ID}"
    )


def _parse_geos(offer: Offer) -> list[str]:
    if not offer.geo:
        return []
    return [g.strip().upper() for g in offer.geo.split(",") if g.strip()]


def _log_decision(
    scope: str,
    target_id: str,
    action: str,
    reason: str,
    data: dict,
) -> None:
    db.execute(
        "INSERT INTO decisions (scope, target_id, action, reason, data_json) VALUES (?, ?, ?, ?, ?)",
        (scope, target_id, action, reason, json.dumps(data)),
    )


def launch_campaign(offer: Offer, daily_cap: Optional[float] = None) -> Campaign:
    """Launch a PropellerAds push campaign for *offer*, gated by budget.

    Steps:
    1. Guard: refuse if global or daily budget is exhausted.
    2. Generate lander HTML and derive its slug.
    3. Build tracking URL with PropellerAds macros.
    4. Insert pending campaign row in DB.
    5. Generate and persist push creatives in DB.
    6. Create campaign on PropellerAds (daily_budget set in payload).
    7. Mirror daily budget cap via set_daily_budget (defense in depth).
    8. Upload creatives; persist traffic_creative_id back to DB.
    9. Update campaign row with network ID and actual status.
    10. Mark offer as testing; write decisions audit row.

    Returns the persisted Campaign dataclass.
    Raises BudgetExhaustedError when budget guards prevent launch.
    """
    cap = daily_cap if daily_cap is not None else settings.daily_cap

    # 1. Budget guard — single chokepoint, checked before any side effects
    if budget.is_global_exhausted():
        raise BudgetExhaustedError("Global budget exhausted — cannot launch campaign.")
    if not budget.can_spend(cap):
        raise BudgetExhaustedError(
            f"Cannot spend ${cap:.2f}: would exceed global or daily budget cap."
        )

    # 2. Generate lander HTML
    logger.info("Generating lander for offer %r (id=%d)", offer.name, offer.id)
    lander_path = generate_lander(offer)
    slug = _slug(offer)

    # 3. Tracking URL with PropellerAds macros
    tracking_url = _build_tracking_url(slug)

    # 4. Insert pending campaign row so generate_creatives has a campaign_id
    cur = db.execute(
        "INSERT INTO campaigns (offer_id, traffic_campaign_id, lander_path, status, daily_cap)"
        " VALUES (?, NULL, ?, 'pending', ?)",
        (offer.id, lander_path, cap),
    )
    campaign_db_id: int = cur.lastrowid
    logger.info("Inserted campaign row id=%d (pending)", campaign_db_id)

    # 5. Generate and DB-persist push creatives
    logger.info("Generating creatives for campaign %d", campaign_db_id)
    creatives = generate_creatives(offer, campaign_db_id)

    # 6. Create campaign on PropellerAds
    geos = _parse_geos(offer)
    campaign_name = f"ai-money | {offer.name[:40]} | {offer.id}"
    logger.info("Creating PropellerAds campaign: %r", campaign_name)

    traffic_campaign = traffic.create_campaign(
        name=campaign_name,
        landing_url=tracking_url,
        daily_budget=cap,
        bid=0.01,  # conservative starting bid; optimizer scales winners
        country=geos if geos else ["US"],
        format="push",
    )

    network_status = (traffic_campaign.status or "pending").lower()
    local_status = "pending" if network_status in {"pending", "moderation", "review"} else "active"

    # 7. Mirror daily budget cap on network side (defense in depth)
    try:
        traffic.set_daily_budget(traffic_campaign.campaign_id, cap)
    except traffic.TrafficError as exc:
        # Non-fatal: create_campaign already set it; log and continue
        logger.warning("set_daily_budget (defense-in-depth) failed: %s", exc)

    # 8. Upload creatives to the network campaign
    creative_payloads = []
    for c in creatives:
        payload: dict = {"title": c.title, "description": c.description}
        if c.icon_path:
            payload["icon_url"] = f"https://{settings.domain}/{c.icon_path}"
        creative_payloads.append(payload)

    traffic_creatives = []
    try:
        traffic_creatives = traffic.add_creatives(traffic_campaign.campaign_id, creative_payloads)
    except traffic.TrafficError as exc:
        # Campaign is live even without creatives being linked; log prominently
        logger.error(
            "add_creatives failed for network campaign %s: %s",
            traffic_campaign.campaign_id, exc,
        )

    # Persist traffic_creative_id back to DB for each matched creative
    for local_cr, network_cr in zip(creatives, traffic_creatives):
        db.execute(
            "UPDATE creatives SET traffic_creative_id = ? WHERE id = ?",
            (network_cr.creative_id, local_cr.id),
        )

    # 9. Update campaign row with network ID and actual status
    db.execute(
        "UPDATE campaigns SET traffic_campaign_id = ?, status = ? WHERE id = ?",
        (traffic_campaign.campaign_id, local_status, campaign_db_id),
    )

    # 10. Mark offer as testing; write audit decision
    db.execute("UPDATE offers SET status = 'testing' WHERE id = ?", (offer.id,))

    _log_decision(
        scope="campaign",
        target_id=str(campaign_db_id),
        action="launch",
        reason=(
            f"Launched offer {offer.name!r} (id={offer.id}); "
            f"network_status={network_status}; daily_cap=${cap:.2f}"
        ),
        data={
            "offer_id": offer.id,
            "traffic_campaign_id": traffic_campaign.campaign_id,
            "tracking_url": tracking_url,
            "daily_cap": cap,
            "network_status": network_status,
            "local_status": local_status,
            "creatives_count": len(creatives),
            "creatives_uploaded": len(traffic_creatives),
        },
    )

    logger.info(
        "Campaign launched: db_id=%d network_id=%s status=%s daily_cap=$%.2f",
        campaign_db_id, traffic_campaign.campaign_id, local_status, cap,
    )

    row = db.fetchone("SELECT * FROM campaigns WHERE id = ?", (campaign_db_id,))
    return Campaign(
        id=row["id"],
        offer_id=row["offer_id"],
        traffic_campaign_id=row["traffic_campaign_id"],
        lander_path=row["lander_path"],
        status=row["status"],
        daily_cap=float(row["daily_cap"]),
        created_at=row["created_at"],
        notes=row["notes"],
    )
