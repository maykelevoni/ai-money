"""Daily Telegram performance report + alert helper.

send_daily_report() — called by the scheduler once a day.
send_alert(text)     — lightweight push for cap-hit / critical events; reused by optimizer.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date

from src import budget as budget_mod
from src import db
from src.clients import telegram
from src.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_alert(text: str) -> None:
    """Send a short urgent message to Telegram (no formatting wrapper)."""
    telegram.send(text)


def send_daily_report() -> None:
    """Build and deliver the daily summary to Telegram."""
    try:
        msg = _build_report()
    except Exception:
        logger.exception("Failed to build daily report")
        telegram.send("*[Report Error]* Could not build daily report — check engine logs.")
        return
    telegram.send(msg)
    logger.info("Daily report sent to Telegram")


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _build_report() -> str:
    today = date.today().isoformat()

    spend_today = budget_mod.spent_today()
    total_spent = _total_spent_alltime()
    remaining = budget_mod.remaining_global()
    revenue_today = _total_revenue_today()
    net_roi_pct = _roi_pct(spend_today, revenue_today)

    campaigns = _campaign_rows()
    actions = _decision_rows()

    lines: list[str] = []

    lines.append(f"*Daily Report — {today}*")
    lines.append("")

    lines.append("*BUDGET*")
    lines.append(f"Spent today:   ${spend_today:.2f} / ${settings.daily_cap:.2f} cap")
    lines.append(f"Total spent:   ${total_spent:.2f} / ${settings.global_budget:.2f} global")
    lines.append(f"Remaining:     ${remaining:.2f}")
    lines.append("")

    lines.append("*PERFORMANCE*")
    lines.append(f"Revenue today: ${revenue_today:.2f}")
    lines.append(f"Spend today:   ${spend_today:.2f}")
    lines.append(f"Net ROI:       {net_roi_pct}")
    lines.append("")

    lines.append("*CAMPAIGNS*")
    if not campaigns:
        lines.append("No campaign spend or revenue recorded today.")
    else:
        for c in campaigns:
            lines.extend(_format_campaign(c))
    lines.append("")

    lines.append("*ACTIONS TODAY*")
    if not actions:
        lines.append("No optimizer actions recorded today.")
    else:
        for a in actions:
            lines.append(f"• [{a['action'].upper()}] {a['scope']} {a['target_id']}: {a['reason']}")
    lines.append("")

    if remaining <= settings.daily_cap:
        lines.append("*⚠ Budget running low — consider topping up before the engine pauses.*")

    return "\n".join(lines)


def _format_campaign(c: dict) -> list[str]:
    spend = c["spend"]
    revenue = c["revenue"]
    conv = c["conv_count"]
    roi_str = _roi_pct(spend, revenue)
    offer_name = c["offer_name"] or f"Offer #{c['offer_id']}"
    status = c["status"]

    profitable = revenue > spend > 0 and conv >= settings.min_conv

    header = f"Campaign #{c['campaign_id']} | {offer_name} | {status}"
    detail = f"  Spend: ${spend:.2f} | Revenue: ${revenue:.2f} | ROI: {roi_str} | Conv: {conv}"

    out = [header, detail]
    if profitable:
        out.append("  *✅ PROFITABLE — scale me*")
    return out


# ---------------------------------------------------------------------------
# DB queries
# ---------------------------------------------------------------------------

def _total_spent_alltime() -> float:
    row = db.fetchone(
        "SELECT COALESCE(SUM(amount), 0.0) AS total FROM budget_ledger WHERE kind = 'spend'"
    )
    return float(row["total"]) if row else 0.0


def _total_revenue_today() -> float:
    row = db.fetchone(
        "SELECT COALESCE(SUM(cv.payout), 0.0) AS total "
        "FROM conversions cv "
        "WHERE date(cv.ts) = date('now')"
    )
    return float(row["total"]) if row else 0.0


def _campaign_rows() -> list[dict]:
    """Return per-campaign stats for today, sorted by ROI descending (profitable first)."""
    spend_rows = db.fetchall(
        "SELECT campaign_id, COALESCE(SUM(spend), 0.0) AS spend "
        "FROM spend_snapshots "
        "WHERE date(ts) = date('now') "
        "GROUP BY campaign_id"
    )
    spend_by_cid: dict[int, float] = {r["campaign_id"]: float(r["spend"]) for r in spend_rows}

    rev_rows = db.fetchall(
        "SELECT cl.campaign_id, "
        "       COALESCE(SUM(cv.payout), 0.0) AS revenue, "
        "       COUNT(cv.id) AS conv_count "
        "FROM conversions cv "
        "JOIN clicks cl ON cl.click_id = cv.click_id "
        "WHERE date(cv.ts) = date('now') "
        "GROUP BY cl.campaign_id"
    )
    rev_by_cid: dict[int, tuple[float, int]] = {
        r["campaign_id"]: (float(r["revenue"]), int(r["conv_count"])) for r in rev_rows
    }

    camp_rows = db.fetchall(
        "SELECT c.id AS campaign_id, c.offer_id, c.status, o.name AS offer_name "
        "FROM campaigns c "
        "JOIN offers o ON o.id = c.offer_id"
    )

    results = []
    for row in camp_rows:
        cid = row["campaign_id"]
        spend = spend_by_cid.get(cid, 0.0)
        revenue, conv_count = rev_by_cid.get(cid, (0.0, 0))

        if spend == 0.0 and revenue == 0.0:
            continue

        results.append({
            "campaign_id": cid,
            "offer_id": row["offer_id"],
            "offer_name": row["offer_name"],
            "status": row["status"],
            "spend": spend,
            "revenue": revenue,
            "conv_count": conv_count,
        })

    results.sort(key=lambda c: (c["revenue"] - c["spend"]) / c["spend"] if c["spend"] > 0 else 0.0, reverse=True)
    return results


def _decision_rows() -> list[sqlite3.Row]:
    return db.fetchall(
        "SELECT scope, target_id, action, reason "
        "FROM decisions "
        "WHERE date(ts) = date('now') "
        "ORDER BY id"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roi_pct(spend: float, revenue: float) -> str:
    if spend <= 0:
        return "N/A"
    roi = (revenue - spend) / spend * 100
    sign = "+" if roi >= 0 else ""
    return f"{sign}{roi:.1f}%"
