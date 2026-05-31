"""Unit tests for optimizer pure decision functions.

All tests exercise pure functions only — no DB, no live APIs, no config loading.
"""
import pytest

from src.optimize import (
    CreativeReport,
    OptimizerDecision,
    ZoneReport,
    decide_campaign_action,
    decide_creative_pauses,
    decide_zone_blacklists,
)

# ── Shared constants ─────────────────────────────────────────────────────────────

PAYOUT = 2.0
MIN_ZONE_CLICKS = 50
MIN_CREATIVE_CLICKS = 30
MIN_CONV = 2
SCALE_ROI = 0.20
KILL_ROI = -0.50
KILL_SPEND_MULT = 3.0  # KILL_SPEND default (3× payout = $6)


# ── decide_zone_blacklists ───────────────────────────────────────────────────────

def _zone(zone_id: str, spend: float, clicks: int, conversions: int) -> ZoneReport:
    return ZoneReport(
        zone_id=zone_id, spend=spend, clicks=clicks,
        conversions=conversions, revenue=conversions * PAYOUT,
    )


def test_zone_blacklist_fires_at_exact_threshold():
    zones = [_zone("z1", spend=3.0, clicks=50, conversions=0)]  # 1.5×$2 = $3
    decisions = decide_zone_blacklists(zones, PAYOUT, MIN_ZONE_CLICKS)
    assert len(decisions) == 1
    assert decisions[0].action == "blacklist"
    assert decisions[0].target_id == "z1"


def test_zone_blacklist_fires_when_spend_exceeds_threshold():
    zones = [_zone("z2", spend=5.0, clicks=100, conversions=0)]
    decisions = decide_zone_blacklists(zones, PAYOUT, MIN_ZONE_CLICKS)
    assert len(decisions) == 1
    assert decisions[0].target_id == "z2"


def test_zone_no_blacklist_below_min_clicks_gate():
    # spend threshold met, 0 conv, but clicks below gate → no action
    zones = [_zone("z3", spend=3.0, clicks=49, conversions=0)]
    decisions = decide_zone_blacklists(zones, PAYOUT, MIN_ZONE_CLICKS)
    assert decisions == []


def test_zone_no_blacklist_when_has_conversion():
    # threshold met, enough clicks, but has a conversion → keep running
    zones = [_zone("z4", spend=3.0, clicks=50, conversions=1)]
    decisions = decide_zone_blacklists(zones, PAYOUT, MIN_ZONE_CLICKS)
    assert decisions == []


def test_zone_no_blacklist_when_spend_below_threshold():
    # clicks ok, 0 conv, but spend hasn't hit 1.5×payout yet
    zones = [_zone("z5", spend=2.99, clicks=50, conversions=0)]
    decisions = decide_zone_blacklists(zones, PAYOUT, MIN_ZONE_CLICKS)
    assert decisions == []


def test_zone_blacklist_multiple_zones_partial():
    zones = [
        _zone("good", spend=5.0, clicks=80, conversions=1),   # has conv → skip
        _zone("bad1", spend=4.0, clicks=60, conversions=0),   # blacklist
        _zone("bad2", spend=3.0, clicks=50, conversions=0),   # blacklist
        _zone("small", spend=3.0, clicks=10, conversions=0),  # below gate → skip
    ]
    decisions = decide_zone_blacklists(zones, PAYOUT, MIN_ZONE_CLICKS)
    assert len(decisions) == 2
    targets = {d.target_id for d in decisions}
    assert targets == {"bad1", "bad2"}


# ── decide_creative_pauses ───────────────────────────────────────────────────────

def _creative(cid: int, clicks: int, ctr: float, status: str = "active") -> CreativeReport:
    return CreativeReport(
        creative_id=cid, traffic_creative_id=f"tc{cid}",
        clicks=clicks, ctr=ctr, status=status,
    )


def test_creative_pause_fires_for_bottom_third():
    creatives = [
        _creative(1, clicks=50, ctr=0.05),   # top
        _creative(2, clicks=50, ctr=0.03),   # middle
        _creative(3, clicks=50, ctr=0.01),   # bottom → pause
    ]
    decisions = decide_creative_pauses(creatives, MIN_CREATIVE_CLICKS)
    assert len(decisions) == 1
    assert decisions[0].target_id == "3"
    assert decisions[0].action == "pause"


def test_creative_no_pause_below_min_clicks_gate():
    creatives = [
        _creative(1, clicks=50, ctr=0.05),
        _creative(2, clicks=29, ctr=0.01),  # below gate → ineligible
    ]
    # Only one eligible → no pause (keep at least 1)
    decisions = decide_creative_pauses(creatives, MIN_CREATIVE_CLICKS)
    assert decisions == []


def test_creative_no_pause_only_one_eligible():
    # Only one creative with enough clicks → must keep it, no pause
    creatives = [_creative(1, clicks=50, ctr=0.02)]
    decisions = decide_creative_pauses(creatives, MIN_CREATIVE_CLICKS)
    assert decisions == []


def test_creative_pause_skips_already_paused():
    creatives = [
        _creative(1, clicks=50, ctr=0.05),
        _creative(2, clicks=50, ctr=0.04),
        _creative(3, clicks=50, ctr=0.01, status="paused"),  # already paused
    ]
    # Only 2 active eligible; bottom 1 of 2 = creative 2 gets paused
    decisions = decide_creative_pauses(creatives, MIN_CREATIVE_CLICKS)
    assert len(decisions) == 1
    assert decisions[0].target_id == "2"


def test_creative_pause_no_action_below_min_clicks_all():
    creatives = [
        _creative(1, clicks=10, ctr=0.05),
        _creative(2, clicks=10, ctr=0.01),
    ]
    decisions = decide_creative_pauses(creatives, MIN_CREATIVE_CLICKS)
    assert decisions == []


# ── decide_campaign_action: scale ───────────────────────────────────────────────

def _campaign_decision(
    spend: float,
    revenue: float,
    conversions: int,
    payout: float = PAYOUT,
    min_conv: int = MIN_CONV,
    scale_roi: float = SCALE_ROI,
    kill_roi: float = KILL_ROI,
    kill_spend_mult: float = KILL_SPEND_MULT,
) -> OptimizerDecision | None:
    return decide_campaign_action(
        campaign_id=1,
        traffic_campaign_id="tc1",
        offer_id=10,
        total_spend=spend,
        total_revenue=revenue,
        total_conversions=conversions,
        payout=payout,
        min_conv=min_conv,
        scale_roi=scale_roi,
        kill_roi=kill_roi,
        kill_spend_mult=kill_spend_mult,
    )


def test_scale_fires_when_profitable_with_enough_conv():
    # spend=4, revenue=5, ROI=25% ≥ 20%; conv=2 ≥ 2
    decision = _campaign_decision(spend=4.0, revenue=5.0, conversions=2)
    assert decision is not None
    assert decision.action == "scale"


def test_scale_no_action_below_min_conv_gate():
    # Great ROI but only 1 conversion — need MIN_CONV=2
    decision = _campaign_decision(spend=4.0, revenue=5.0, conversions=1)
    assert decision is None


def test_scale_no_action_when_roi_below_threshold():
    # conv ok, but ROI only 10% < 20%
    decision = _campaign_decision(spend=10.0, revenue=11.0, conversions=3)
    assert decision is None


def test_scale_fires_at_exact_roi_threshold():
    # ROI = exactly 20% at conv=2
    decision = _campaign_decision(spend=5.0, revenue=6.0, conversions=2)
    assert decision is not None
    assert decision.action == "scale"


# ── decide_campaign_action: kill ─────────────────────────────────────────────────

def test_kill_fires_when_losing_with_enough_spend():
    # spend=$8 ≥ 3×$2=$6; revenue=0 → ROI=-100% ≤ -50%
    decision = _campaign_decision(spend=8.0, revenue=0.0, conversions=0)
    assert decision is not None
    assert decision.action == "kill"


def test_kill_no_action_below_min_spend_gate():
    # ROI is terrible but spend hasn't hit 3×payout=$6 yet
    decision = _campaign_decision(spend=5.0, revenue=0.0, conversions=0)
    assert decision is None


def test_kill_no_action_when_roi_above_kill_threshold():
    # spend ≥ 3×payout, but ROI is only -20% > -50% → not bad enough to kill
    decision = _campaign_decision(spend=8.0, revenue=6.4, conversions=1)
    assert decision is None


def test_kill_fires_at_exact_roi_threshold():
    # spend=$6=$3×$2, ROI=-50% exactly
    decision = _campaign_decision(spend=6.0, revenue=3.0, conversions=0)
    assert decision is not None
    assert decision.action == "kill"


def test_no_action_when_spend_zero():
    decision = _campaign_decision(spend=0.0, revenue=0.0, conversions=0)
    assert decision is None


# ── Scale takes priority over kill when both might apply ─────────────────────────

def test_scale_takes_priority():
    # Meets scale thresholds; even though it also has enough spend for kill check,
    # ROI is positive so kill won't fire.
    decision = _campaign_decision(spend=6.0, revenue=8.0, conversions=2)
    assert decision is not None
    assert decision.action == "scale"


# ── Decision reason and data fields ──────────────────────────────────────────────

def test_zone_decision_has_data_fields():
    zones = [_zone("z99", spend=4.0, clicks=60, conversions=0)]
    decisions = decide_zone_blacklists(zones, PAYOUT, MIN_ZONE_CLICKS)
    assert decisions[0].data["spend"] == 4.0
    assert decisions[0].data["clicks"] == 60
    assert "threshold" in decisions[0].data
    assert "z99" in decisions[0].reason


def test_campaign_scale_decision_has_data_fields():
    decision = _campaign_decision(spend=4.0, revenue=5.0, conversions=2)
    assert decision is not None
    assert "roi" in decision.data
    assert "spend" in decision.data
    assert "revenue" in decision.data
    assert "conversions" in decision.data


def test_campaign_kill_decision_has_data_fields():
    decision = _campaign_decision(spend=8.0, revenue=0.0, conversions=0)
    assert decision is not None
    assert "roi" in decision.data
    assert "offer_id" in decision.data
    assert decision.data["offer_id"] == 10
