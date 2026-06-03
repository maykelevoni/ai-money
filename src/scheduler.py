"""APScheduler jobs — the always-on autonomous engine."""
from __future__ import annotations

import functools
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src import budget, config, db, offers, optimize, report
from src.clients import telegram, traffic

logger = logging.getLogger(__name__)

_OPTIMIZE_HOURS = int(os.getenv("OPTIMIZE_INTERVAL_HOURS", "3"))
_BUDGET_GUARD_MINUTES = int(os.getenv("BUDGET_GUARD_MINUTES", "15"))
_REPORT_HOUR_UTC = int(os.getenv("REPORT_HOUR_UTC", "8"))
_TARGET_ACTIVE_CAMPAIGNS = int(os.getenv("TARGET_ACTIVE_CAMPAIGNS", "3"))


def _safe(fn):
    """Wrap a job: log + swallow exceptions so a failing run never kills the scheduler."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception:
            logger.exception("Scheduler job %r failed — will retry on next tick", fn.__name__)
    return wrapper


def _engine_ready(job_name: str) -> bool:
    """Engine jobs idle (with a clear log) until their integration keys are set."""
    if config.is_engine_configured():
        return True
    logger.info(
        "%s: engine idle — waiting on keys: %s",
        job_name, ", ".join(config.missing_engine_keys()),
    )
    return False


@_safe
def launch_job() -> None:
    """Daily: sync offers and launch a campaign when below the active-campaign target."""
    if not _engine_ready("launch_job"):
        return
    from src import launch  # deferred to avoid import-time side-effects from generate

    row = db.fetchone("SELECT COUNT(*) AS cnt FROM campaigns WHERE status = 'active'")
    active_count = int(row["cnt"]) if row else 0

    if active_count >= _TARGET_ACTIVE_CAMPAIGNS:
        logger.info(
            "launch_job: %d active campaigns (target=%d) — no launch needed",
            active_count, _TARGET_ACTIVE_CAMPAIGNS,
        )
        return

    logger.info(
        "launch_job: %d/%d active — syncing offers and launching",
        active_count, _TARGET_ACTIVE_CAMPAIGNS,
    )
    offers.sync_offers()
    offer = offers.pick_next_offer()
    if offer is None:
        logger.warning("launch_job: no candidate offers available after sync")
        return

    campaign = launch.launch_campaign(offer)
    logger.info("launch_job: launched campaign id=%d", campaign.id)


@_safe
def optimize_job() -> None:
    """Every N hours: run one optimizer cycle."""
    if not _engine_ready("optimize_job"):
        return
    logger.info("optimize_job: starting optimizer cycle")
    optimize.run_optimizer()


@_safe
def report_job() -> None:
    """Daily at REPORT_HOUR_UTC: deliver Telegram daily report."""
    if not config.settings.telegram_bot_token:
        logger.info("report_job: no Telegram token configured — skipping report")
        return
    logger.info("report_job: sending daily report")
    report.send_daily_report()


@_safe
def affiliate_validate_job() -> None:
    """Every 8h: validate and enrich affiliate product candidates."""
    if not config.has_digistore():
        logger.info("affiliate_validate_job: idle — Digistore24 key not configured")
        return
    from src import affiliate_research  # deferred to avoid import-time side-effects
    logger.info("affiliate_validate_job: starting validation + enrichment")
    affiliate_research.validate_and_enrich()


@_safe
def affiliate_pagegen_job() -> None:
    """Daily: generate promotion pages for pending affiliate products."""
    if not config.has_digistore():
        logger.info("affiliate_pagegen_job: idle — Digistore24 key not configured")
        return
    from src import affiliate_generate  # deferred to avoid import-time side-effects
    logger.info("affiliate_pagegen_job: generating pending affiliate pages")
    affiliate_generate.generate_pending(limit=3)


@_safe
def budget_guard_job() -> None:
    """Every 15m: pause all campaigns and alert if any budget cap is hit."""
    if not (budget.is_global_exhausted() or budget.is_daily_exhausted()):
        return

    reason = "global" if budget.is_global_exhausted() else "daily"
    logger.warning("budget_guard_job: %s budget cap hit — pausing all active campaigns", reason)

    rows = db.fetchall(
        "SELECT id, traffic_campaign_id FROM campaigns WHERE status = 'active'"
    )
    for row in rows:
        if row["traffic_campaign_id"]:
            try:
                traffic.pause_campaign(row["traffic_campaign_id"])
            except Exception:
                logger.exception(
                    "budget_guard_job: API pause failed for campaign %s", row["id"]
                )
        db.execute("UPDATE campaigns SET status = 'paused' WHERE id = ?", (row["id"],))

    msg = (
        "⚠️ *Budget alert*: global budget exhausted. All campaigns paused."
        if reason == "global"
        else "ℹ️ *Budget*: daily cap reached. Campaigns paused until tomorrow."
    )
    telegram.send(msg)


def create_scheduler() -> AsyncIOScheduler:
    """Build and return the configured APScheduler instance (not yet started)."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        launch_job,
        trigger=IntervalTrigger(hours=24),
        id="launch_job",
        name="Daily campaign launcher",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        optimize_job,
        trigger=IntervalTrigger(hours=_OPTIMIZE_HOURS),
        id="optimize_job",
        name=f"Optimizer cycle (every {_OPTIMIZE_HOURS}h)",
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        report_job,
        trigger=CronTrigger(hour=_REPORT_HOUR_UTC, minute=0, timezone="UTC"),
        id="report_job",
        name=f"Daily Telegram report ({_REPORT_HOUR_UTC:02d}:00 UTC)",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        budget_guard_job,
        trigger=IntervalTrigger(minutes=_BUDGET_GUARD_MINUTES),
        id="budget_guard_job",
        name=f"Budget cap guard (every {_BUDGET_GUARD_MINUTES}m)",
        misfire_grace_time=300,
    )
    scheduler.add_job(
        affiliate_validate_job,
        trigger=IntervalTrigger(hours=8),
        id="affiliate_validate_job",
        name="Affiliate product validation + enrichment (every 8h)",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        affiliate_pagegen_job,
        trigger=IntervalTrigger(hours=24),
        id="affiliate_pagegen_job",
        name="Affiliate page generation (daily)",
        misfire_grace_time=3600,
    )

    logger.info(
        "Scheduler configured: launch (daily), optimize (every %dh), "
        "report (%02d:00 UTC daily), budget_guard (every %dm), "
        "affiliate_validate (every 8h), affiliate_pagegen (daily)",
        _OPTIMIZE_HOURS, _REPORT_HOUR_UTC, _BUDGET_GUARD_MINUTES,
    )
    return scheduler
