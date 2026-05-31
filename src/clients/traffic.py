"""PropellerAds SSP API v5 wrapper — advertiser/campaign management.

Endpoints confirmed in spike/FINDINGS.md. No business logic here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from src.config import settings

PROPELLER_BASE = "https://ssp-api.propellerads.com/v5"

_TIMEOUT = httpx.Timeout(20.0)
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


# ── Typed errors ───────────────────────────────────────────────────────────────

class TrafficError(Exception):
    pass


class TrafficAuthError(TrafficError):
    pass


class TrafficRateLimitError(TrafficError):
    pass


class TrafficNotFoundError(TrafficError):
    pass


# ── Return types ───────────────────────────────────────────────────────────────

@dataclass
class CampaignRecord:
    campaign_id: str
    name: str
    status: str       # "active" | "stopped" | "paused" | "pending"
    daily_budget: float
    bid: float


@dataclass
class CreativeRecord:
    creative_id: str
    campaign_id: str
    title: str
    description: str
    status: str


@dataclass
class ZoneStat:
    zone_id: str
    clicks: int
    impressions: int
    spend: float
    ctr: float


# ── Internal helpers ───────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.propellerads_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _retry(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    for attempt in range(_MAX_RETRIES):
        resp = client.request(method, url, **kwargs)
        if resp.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
            time.sleep(2 ** attempt)
            continue
        return resp
    return resp  # type: ignore[return-value]


def _raise_for_traffic(resp: httpx.Response, context: str) -> None:
    if resp.status_code == 401:
        raise TrafficAuthError(f"{context}: 401 Unauthorized — check PROPELLERADS_API_KEY")
    if resp.status_code == 404:
        raise TrafficNotFoundError(f"{context}: 404 Not Found")
    if resp.status_code == 429:
        raise TrafficRateLimitError(f"{context}: 429 Rate limit exceeded")
    if not resp.is_success:
        raise TrafficError(f"{context}: HTTP {resp.status_code} — {resp.text[:300]}")


def _normalize_campaign(raw: dict) -> CampaignRecord:
    return CampaignRecord(
        campaign_id=str(raw.get("id") or raw.get("campaign_id") or ""),
        name=raw.get("name") or "",
        status=raw.get("status") or "",
        daily_budget=float(raw.get("daily_budget") or 0.0),
        bid=float(raw.get("bid") or 0.0),
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def create_campaign(
    name: str,
    landing_url: str,
    daily_budget: float,
    bid: float,
    country: list[str],
    format: str = "push",
    bid_type: str = "CPC",
    os: list[str] | None = None,
    browser: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> CampaignRecord:
    """Create a new PropellerAds campaign and return the normalized result.

    landing_url should include PropellerAds macro tokens:
        ?zone={ZONE_ID}&cost={COST}&country={COUNTRY}&cid={CLICK_ID}
    """
    payload: dict[str, Any] = {
        "name": name,
        "status": "active",
        "bid_type": bid_type,
        "bid": bid,
        "daily_budget": daily_budget,
        "country": country,
        "format": format,
        "landing_url": landing_url,
    }
    if os is not None:
        payload["os"] = os
    if browser is not None:
        payload["browser"] = browser
    if extra:
        payload.update(extra)

    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = _retry(client, "POST", f"{PROPELLER_BASE}/adv/campaigns", headers=_headers(), json=payload)
    _raise_for_traffic(resp, "create_campaign")
    return _normalize_campaign(resp.json())


def add_creatives(
    campaign_id: str,
    creatives: list[dict[str, Any]],
) -> list[CreativeRecord]:
    """Add push creatives to an existing campaign.

    Each creative dict should have: title, description, and optionally icon_url.
    Push title ≤ ~30 chars; description ≤ ~45 chars.
    """
    results: list[CreativeRecord] = []
    with httpx.Client(timeout=_TIMEOUT) as client:
        for creative in creatives:
            resp = _retry(
                client, "POST",
                f"{PROPELLER_BASE}/adv/campaigns/{campaign_id}/creatives",
                headers=_headers(),
                json=creative,
            )
            _raise_for_traffic(resp, f"add_creatives(campaign={campaign_id})")
            raw = resp.json()
            results.append(CreativeRecord(
                creative_id=str(raw.get("id") or raw.get("creative_id") or ""),
                campaign_id=campaign_id,
                title=raw.get("title") or creative.get("title") or "",
                description=raw.get("description") or creative.get("description") or "",
                status=raw.get("status") or "pending",
            ))
    return results


def set_daily_budget(campaign_id: str, amount: float) -> None:
    """Update the daily budget cap for a campaign.

    PATCH /adv/campaigns/{id} with {"daily_budget": amount}.
    """
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = _retry(
            client, "PATCH",
            f"{PROPELLER_BASE}/adv/campaigns/{campaign_id}",
            headers=_headers(),
            json={"daily_budget": amount},
        )
    _raise_for_traffic(resp, f"set_daily_budget(campaign={campaign_id})")


def pause_campaign(campaign_id: str) -> None:
    """Pause a campaign by setting its status to stopped.

    PATCH /adv/campaigns/{id} with {"status": "stopped"}.
    """
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = _retry(
            client, "PATCH",
            f"{PROPELLER_BASE}/adv/campaigns/{campaign_id}",
            headers=_headers(),
            json={"status": "stopped"},
        )
    _raise_for_traffic(resp, f"pause_campaign(campaign={campaign_id})")


def exclude_zone(campaign_id: str, zone: str) -> None:
    """Add a zone to the campaign's blacklist.

    Primary: POST /adv/blacklists with campaign_id + zone_id.
    Fallback: POST /adv/campaigns/{id}/blacklist_zones if the primary returns 404.
    (Spike FINDINGS.md notes uncertainty about which endpoint is active on v5.)
    """
    payload = {"campaign_id": campaign_id, "zone_id": zone}
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = _retry(client, "POST", f"{PROPELLER_BASE}/adv/blacklists", headers=_headers(), json=payload)
        if resp.status_code == 404:
            resp = _retry(
                client, "POST",
                f"{PROPELLER_BASE}/adv/campaigns/{campaign_id}/blacklist_zones",
                headers=_headers(),
                json={"zone_id": zone},
            )
    _raise_for_traffic(resp, f"exclude_zone(campaign={campaign_id}, zone={zone})")


def get_zone_stats(campaign_id: str) -> list[ZoneStat]:
    """Fetch per-zone statistics for a campaign (today's date window).

    GET /adv/statistics/campaigns?campaign_id=&group_by=zone&date_from=&date_to=
    """
    today = date.today().isoformat()
    params = {
        "campaign_id": campaign_id,
        "group_by": "zone",
        "date_from": today,
        "date_to": today,
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = _retry(
            client, "GET",
            f"{PROPELLER_BASE}/adv/statistics/campaigns",
            headers=_headers(),
            params=params,
        )
    _raise_for_traffic(resp, f"get_zone_stats(campaign={campaign_id})")

    data = resp.json()
    rows = data if isinstance(data, list) else data.get("data", data.get("results", []))
    return [
        ZoneStat(
            zone_id=str(row.get("zone_id") or row.get("zone") or ""),
            clicks=int(row.get("clicks") or 0),
            impressions=int(row.get("impressions") or 0),
            spend=float(row.get("spend") or row.get("cost") or 0.0),
            ctr=float(row.get("ctr") or 0.0),
        )
        for row in rows
    ]
