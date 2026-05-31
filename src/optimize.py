"""Optimizer loop — blacklist zones, pause creatives, scale/kill campaigns.

Core decision functions are pure (no I/O) for unit-testability. run_optimizer()
coordinates them with live DB/API calls.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from src import budget
from src.clients import telegram
from src.clients.traffic import (
    ZoneStat,
    exclude_zone,
    get_zone_stats,
    pause_campaign as traffic_pause_campaign,
    set_daily_budget,
)
from src.config import settings
from src.db import execute, fetchall, fetchone

logger = logging.getLogger(__name__)


# ── Pure data types ──────────────────────────────────────────────────────────────

@dataclass
class ZoneReport:
    zone_id: str
    spend: float
    clicks: int
    conversions: int
    revenue: float


@dataclass
class CreativeReport:
    creative_id: int
    traffic_creative_id: str
    clicks: int
    ctr: float
    status: str


@dataclass
class OptimizerDecision:
    scope: str       # zone|creative|campaign|offer
    target_id: str
    action: str      # pause|scale|blacklist|kill
    reason: str
    data: dict = field(default_factory=dict)


# ── Pure decision functions (no I/O — unit-testable) ────────────────────────────

def decide_zone_blacklists(
    zones: list[ZoneReport],
    payout: float,
    min_zone_clicks: int,
    spend_mult: float = 1.5,
) -> list[OptimizerDecision]:
    """Blacklist zones that burned ≥spend_mult×payout with 0 conversions."""
    threshold = spend_mult * payout
    decisions = []
    for z in zones:
        if z.clicks >= min_zone_clicks and z.conversions == 0 and z.spend >= threshold:
            decisions.append(OptimizerDecision(
                scope="zone",
                target_id=z.zone_id,
                action="blacklist",
                reason=(
                    f"zone {z.zone_id}: ${z.spend:.2f} spend, {z.clicks} clicks, "
                    f"0 conv (≥${threshold:.2f} threshold)"
                ),
                data={"spend": z.spend, "clicks": z.clicks, "threshold": threshold},
            ))
    return decisions


def decide_creative_pauses(
    creatives: list[CreativeReport],
    min_creative_clicks: int,
) -> list[OptimizerDecision]:
    """Pause the bottom-third CTR creatives once they have min clicks.

    Always keeps at least one creative active.
    """
    eligible = [
        c for c in creatives
        if c.clicks >= min_creative_clicks and c.status == "active"
    ]
    if len(eligible) < 2:
        return []

    eligible.sort(key=lambda c: c.ctr, reverse=True)
    cutoff = max(1, len(eligible) // 3)
    bottom = eligible[-cutoff:]

    return [
        OptimizerDecision(
            scope="creative",
            target_id=str(c.creative_id),
            action="pause",
            reason=(
                f"creative {c.traffic_creative_id}: CTR {c.ctr:.4f} "
                f"in bottom tier ({c.clicks} clicks)"
            ),
            data={"ctr": c.ctr, "clicks": c.clicks},
        )
        for c in bottom
    ]


def decide_campaign_action(
    campaign_id: int,
    traffic_campaign_id: str,
    offer_id: int,
    total_spend: float,
    total_revenue: float,
    total_conversions: int,
    payout: float,
    min_conv: int,
    scale_roi: float,
    kill_roi: float,
    kill_spend_mult: float,
) -> OptimizerDecision | None:
    """Return a scale or kill decision, or None if thresholds are not met."""
    if total_spend == 0:
        return None

    roi = (total_revenue - total_spend) / total_spend
    kill_spend_threshold = kill_spend_mult * payout

    if total_conversions >= min_conv and roi >= scale_roi:
        return OptimizerDecision(
            scope="campaign",
            target_id=str(campaign_id),
            action="scale",
            reason=(
                f"campaign {campaign_id}: ROI {roi:.1%}, {total_conversions} conv "
                f"(min {min_conv} conv, ROI ≥{scale_roi:.1%})"
            ),
            data={
                "roi": roi,
                "spend": total_spend,
                "revenue": total_revenue,
                "conversions": total_conversions,
                "traffic_campaign_id": traffic_campaign_id,
            },
        )

    if total_spend >= kill_spend_threshold and roi <= kill_roi:
        return OptimizerDecision(
            scope="campaign",
            target_id=str(campaign_id),
            action="kill",
            reason=(
                f"campaign {campaign_id}: ROI {roi:.1%}, spend ${total_spend:.2f} "
                f"≥${kill_spend_threshold:.2f}, ROI ≤{kill_roi:.1%}"
            ),
            data={
                "roi": roi,
                "spend": total_spend,
                "revenue": total_revenue,
                "kill_spend_threshold": kill_spend_threshold,
                "offer_id": offer_id,
                "traffic_campaign_id": traffic_campaign_id,
            },
        )

    return None


# ── DB helpers ───────────────────────────────────────────────────────────────────

def _log_decision(decision: OptimizerDecision) -> None:
    execute(
        "INSERT INTO decisions (scope, target_id, action, reason, data_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (decision.scope, decision.target_id, decision.action,
         decision.reason, json.dumps(decision.data)),
    )


def _upsert_spend_snapshots(campaign_id: int, zone_stats: list[ZoneStat]) -> float:
    """Insert new snapshots; return incremental spend delta since last run."""
    total_delta = 0.0
    for zs in zone_stats:
        last = fetchone(
            "SELECT spend FROM spend_snapshots "
            "WHERE campaign_id = ? AND zone = ? ORDER BY id DESC LIMIT 1",
            (campaign_id, zs.zone_id),
        )
        last_spend = float(last["spend"]) if last else 0.0
        delta = max(0.0, zs.spend - last_spend)
        total_delta += delta
        execute(
            "INSERT INTO spend_snapshots (campaign_id, zone, spend, clicks) VALUES (?, ?, ?, ?)",
            (campaign_id, zs.zone_id, zs.spend, zs.clicks),
        )
    return total_delta


def _get_zone_reports(campaign_id: int, zone_stats: list[ZoneStat]) -> list[ZoneReport]:
    """Merge fresh API zone stats with DB conversion data."""
    reports = []
    for zs in zone_stats:
        row = fetchone(
            "SELECT COUNT(cv.id) AS convs, COALESCE(SUM(cv.payout), 0.0) AS revenue "
            "FROM clicks cl "
            "LEFT JOIN conversions cv ON cv.click_id = cl.click_id "
            "WHERE cl.campaign_id = ? AND cl.zone = ?",
            (campaign_id, zs.zone_id),
        )
        reports.append(ZoneReport(
            zone_id=zs.zone_id,
            spend=zs.spend,
            clicks=zs.clicks,
            conversions=int(row["convs"]) if row else 0,
            revenue=float(row["revenue"]) if row else 0.0,
        ))
    return reports


def _get_campaign_totals(campaign_id: int) -> tuple[float, float, int]:
    """Return (total_spend, total_revenue, total_conversions) from DB."""
    spend_row = fetchone(
        "SELECT COALESCE(MAX(ss.spend_sum), 0.0) AS total "
        "FROM (SELECT zone, MAX(spend) AS spend_sum "
        "      FROM spend_snapshots WHERE campaign_id = ? GROUP BY zone) ss",
        (campaign_id,),
    )
    revenue_row = fetchone(
        "SELECT COALESCE(SUM(cv.payout), 0.0) AS total, COUNT(cv.id) AS count "
        "FROM clicks cl "
        "JOIN conversions cv ON cv.click_id = cl.click_id "
        "WHERE cl.campaign_id = ?",
        (campaign_id,),
    )
    total_spend = float(spend_row["total"]) if spend_row else 0.0
    total_revenue = float(revenue_row["total"]) if revenue_row else 0.0
    total_conversions = int(revenue_row["count"]) if revenue_row else 0
    return total_spend, total_revenue, total_conversions


def _get_creative_reports(campaign_id: int) -> list[CreativeReport]:
    rows = fetchall(
        "SELECT id, traffic_creative_id, clicks, ctr, status "
        "FROM creatives WHERE campaign_id = ?",
        (campaign_id,),
    )
    return [
        CreativeReport(
            creative_id=row["id"],
            traffic_creative_id=row["traffic_creative_id"] or "",
            clicks=row["clicks"],
            ctr=row["ctr"],
            status=row["status"],
        )
        for row in rows
    ]


def _pause_all_campaigns() -> None:
    rows = fetchall(
        "SELECT id, traffic_campaign_id FROM campaigns WHERE status = 'active'"
    )
    for row in rows:
        if row["traffic_campaign_id"]:
            try:
                traffic_pause_campaign(row["traffic_campaign_id"])
            except Exception as exc:
                logger.warning("API pause failed for campaign %s: %s", row["id"], exc)
        execute("UPDATE campaigns SET status = 'paused' WHERE id = ?", (row["id"],))
        _log_decision(OptimizerDecision(
            scope="campaign",
            target_id=str(row["id"]),
            action="pause",
            reason="budget cap exhausted — emergency pause",
            data={},
        ))


# ── Coordinator (I/O bound) ──────────────────────────────────────────────────────

def _process_campaign(
    campaign_id: int,
    traffic_id: str,
    daily_cap: float,
    offer_id: int,
    payout: float,
) -> None:
    zone_stats = get_zone_stats(traffic_id)
    if not zone_stats:
        logger.debug("No zone stats returned for campaign %s", campaign_id)
        return

    incremental_spend = _upsert_spend_snapshots(campaign_id, zone_stats)
    if incremental_spend > 0:
        budget.record_spend(incremental_spend)

    # Re-check after recording new spend
    if budget.is_global_exhausted():
        logger.warning("Global budget exhausted mid-cycle")
        _pause_all_campaigns()
        telegram.send("⚠️ *Budget alert*: global budget exhausted. All campaigns paused.")
        return

    zone_reports = _get_zone_reports(campaign_id, zone_stats)

    # Zone blacklist
    for decision in decide_zone_blacklists(zone_reports, payout, settings.min_zone_clicks):
        try:
            exclude_zone(traffic_id, decision.target_id)
            _log_decision(decision)
            logger.info("Blacklisted zone %s for campaign %s", decision.target_id, campaign_id)
        except Exception as exc:
            logger.error("exclude_zone(%s) failed: %s", decision.target_id, exc)

    # Creative pause
    for decision in decide_creative_pauses(
        _get_creative_reports(campaign_id), settings.min_creative_clicks
    ):
        execute(
            "UPDATE creatives SET status = 'paused' WHERE id = ?",
            (int(decision.target_id),),
        )
        _log_decision(decision)
        logger.info("Paused creative %s for campaign %s", decision.target_id, campaign_id)

    # Campaign scale / kill
    total_spend, total_revenue, total_conversions = _get_campaign_totals(campaign_id)
    campaign_decision = decide_campaign_action(
        campaign_id=campaign_id,
        traffic_campaign_id=traffic_id,
        offer_id=offer_id,
        total_spend=total_spend,
        total_revenue=total_revenue,
        total_conversions=total_conversions,
        payout=payout,
        min_conv=settings.min_conv,
        scale_roi=settings.scale_roi,
        kill_roi=settings.kill_roi,
        kill_spend_mult=settings.kill_spend,
    )

    if campaign_decision:
        _apply_campaign_decision(campaign_id, traffic_id, daily_cap, offer_id, campaign_decision)


def _apply_campaign_decision(
    campaign_id: int,
    traffic_id: str,
    current_daily_cap: float,
    offer_id: int,
    decision: OptimizerDecision,
) -> None:
    if decision.action == "scale":
        new_cap = min(
            round(current_daily_cap * 1.5, 2),
            round(current_daily_cap + budget.remaining_global(), 2),
        )
        try:
            set_daily_budget(traffic_id, new_cap)
            execute("UPDATE campaigns SET daily_cap = ? WHERE id = ?", (new_cap, campaign_id))
            _log_decision(decision)
            logger.info(
                "Scaled campaign %s: $%.2f → $%.2f/day", campaign_id, current_daily_cap, new_cap
            )
        except Exception as exc:
            logger.error("scale campaign %s failed: %s", campaign_id, exc)

    elif decision.action == "kill":
        try:
            traffic_pause_campaign(traffic_id)
            execute("UPDATE campaigns SET status = 'killed' WHERE id = ?", (campaign_id,))
            execute("UPDATE offers SET status = 'loser' WHERE id = ?", (offer_id,))
            _log_decision(decision)
            logger.info("Killed campaign %s, offer %s marked loser", campaign_id, offer_id)
        except Exception as exc:
            logger.error("kill campaign %s failed: %s", campaign_id, exc)


def run_optimizer() -> None:
    """Run one optimizer cycle across all active campaigns."""
    logger.info("Optimizer cycle starting")

    if budget.is_global_exhausted():
        logger.warning("Global budget exhausted — pausing all campaigns")
        _pause_all_campaigns()
        telegram.send("⚠️ *Budget alert*: global budget exhausted. All campaigns paused.")
        return

    if budget.is_daily_exhausted():
        logger.info("Daily cap reached — pausing campaigns until tomorrow")
        _pause_all_campaigns()
        telegram.send("ℹ️ *Budget*: daily cap reached. Campaigns paused until tomorrow.")
        return

    campaigns = fetchall(
        "SELECT c.id, c.traffic_campaign_id, c.daily_cap, c.offer_id, o.payout "
        "FROM campaigns c "
        "JOIN offers o ON o.id = c.offer_id "
        "WHERE c.status = 'active' AND c.traffic_campaign_id IS NOT NULL"
    )

    for camp in campaigns:
        try:
            _process_campaign(
                campaign_id=camp["id"],
                traffic_id=camp["traffic_campaign_id"],
                daily_cap=float(camp["daily_cap"]),
                offer_id=camp["offer_id"],
                payout=float(camp["payout"]),
            )
        except Exception as exc:
            logger.error("Error in campaign %s optimizer cycle: %s", camp["id"], exc)

    logger.info("Optimizer cycle complete")
