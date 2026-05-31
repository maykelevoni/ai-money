"""CPA network API wrappers — MyLead (primary) and CPALead (fallback).

Returns normalized dataclasses; raises typed errors on failure.
No business logic here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.config import settings

MYLEAD_BASE = "https://api.mylead.global/api/v1"
CPALEAD_BASE = "https://api.cpalead.com"

_TIMEOUT = httpx.Timeout(15.0)
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


# ── Typed errors ───────────────────────────────────────────────────────────────

class CPAError(Exception):
    pass


class CPAAuthError(CPAError):
    pass


class CPARateLimitError(CPAError):
    pass


# ── Return types ───────────────────────────────────────────────────────────────

@dataclass
class OfferRecord:
    """Normalized CPA offer from any supported network.

    offer_id is prefixed with the network name, e.g. "mylead:123" or "cpalead:456".
    tracking_url_template contains {subid} as a placeholder for the caller's click_id.
    """
    offer_id: str      # "network:raw_id"
    network: str       # "mylead" | "cpalead"
    name: str
    vertical: str
    payout: float
    geo: list[str]
    tracking_url_template: str  # URL with {subid} placeholder


# ── Internal helpers ───────────────────────────────────────────────────────────

def _retry(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    for attempt in range(_MAX_RETRIES):
        resp = client.request(method, url, **kwargs)
        if resp.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
            time.sleep(2 ** attempt)
            continue
        return resp
    return resp  # type: ignore[return-value]  # loop always assigns resp


def _raise_for_cpa(resp: httpx.Response, context: str) -> None:
    if resp.status_code == 401:
        raise CPAAuthError(f"{context}: 401 Unauthorized — check API key")
    if resp.status_code == 429:
        raise CPARateLimitError(f"{context}: 429 Rate limit exceeded")
    if not resp.is_success:
        raise CPAError(f"{context}: HTTP {resp.status_code} — {resp.text[:300]}")


def _normalize_mylead(raw: dict) -> OfferRecord:
    geo = raw.get("geo") or raw.get("countries") or []
    if isinstance(geo, str):
        geo = [geo]

    raw_id = str(raw.get("id") or raw.get("offer_id") or "")
    tracking_url = raw.get("tracking_url") or raw.get("url") or ""
    if tracking_url and "{subid}" not in tracking_url and "subid" not in tracking_url:
        sep = "&" if "?" in tracking_url else "?"
        tracking_url = f"{tracking_url}{sep}subid={{subid}}"

    return OfferRecord(
        offer_id=f"mylead:{raw_id}",
        network="mylead",
        name=raw.get("name") or raw.get("title") or "",
        vertical=raw.get("category") or raw.get("vertical") or raw.get("type") or "",
        payout=float(raw.get("payout") or raw.get("commission") or 0.0),
        geo=list(geo),
        tracking_url_template=tracking_url,
    )


def _normalize_cpalead(raw: dict) -> OfferRecord:
    geo = raw.get("geoip") or raw.get("geo") or []
    if isinstance(geo, str):
        geo = [g.strip() for g in geo.split(",") if g.strip()]

    raw_id = str(raw.get("id") or raw.get("offer_id") or "")
    aff_id = settings.cpalead_affiliate_id
    tracking_url = f"https://cpalead.com/go.php?o={raw_id}&u={aff_id}&s={{subid}}"

    return OfferRecord(
        offer_id=f"cpalead:{raw_id}",
        network="cpalead",
        name=raw.get("name") or raw.get("title") or "",
        vertical=raw.get("category") or raw.get("type") or "",
        payout=float(raw.get("payout") or raw.get("cpa_rate") or 0.0),
        geo=list(geo),
        tracking_url_template=tracking_url,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def list_offers(filters: dict[str, Any] | None = None) -> list[OfferRecord]:
    """Return all available offers from every configured CPA network.

    Supported filters:
        geo (str): ISO country code to filter by, e.g. "US"
        vertical (str): category substring to keep, e.g. "leadgen"
        min_payout (float): minimum payout threshold
    """
    filters = filters or {}
    offers: list[OfferRecord] = []

    if settings.mylead_api_key:
        offers.extend(_list_mylead(filters))

    if settings.cpalead_affiliate_id:
        offers.extend(_list_cpalead(filters))

    min_payout = float(filters.get("min_payout", 0.0))
    if min_payout:
        offers = [o for o in offers if o.payout >= min_payout]

    vertical_filter = (filters.get("vertical") or "").lower()
    if vertical_filter:
        offers = [o for o in offers if vertical_filter in o.vertical.lower()]

    return offers


def _list_mylead(filters: dict[str, Any]) -> list[OfferRecord]:
    headers = {
        "Authorization": f"Bearer {settings.mylead_api_key}",
        "Accept": "application/json",
    }
    params: dict[str, Any] = {}
    if "geo" in filters:
        params["country"] = filters["geo"]

    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = _retry(client, "GET", f"{MYLEAD_BASE}/offers", headers=headers, params=params)
    _raise_for_cpa(resp, "MyLead list_offers")

    data = resp.json()
    raw_offers = data if isinstance(data, list) else data.get("data", data.get("offers", []))
    return [_normalize_mylead(o) for o in raw_offers]


def _list_cpalead(filters: dict[str, Any]) -> list[OfferRecord]:
    params: dict[str, Any] = {
        "id": settings.cpalead_affiliate_id,
        "ua": "",
        "geoip": filters.get("geo", ""),
    }

    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = _retry(client, "GET", f"{CPALEAD_BASE}/campaign_json_load_offers.php", params=params)
    _raise_for_cpa(resp, "CPALead list_offers")

    data = resp.json()
    raw_offers = data if isinstance(data, list) else data.get("offers", [])
    return [_normalize_cpalead(o) for o in raw_offers]


def get_tracking_url(offer_id: str) -> str:
    """Return the CPA tracking URL template for an offer.

    The URL contains {subid} as a placeholder; callers replace it with the
    actual click_id UUID when building the CTA redirect link.

    offer_id must be in "network:raw_id" format as returned by list_offers().
    """
    if offer_id.startswith("mylead:"):
        return _mylead_tracking_url(offer_id.removeprefix("mylead:"))
    if offer_id.startswith("cpalead:"):
        return _cpalead_tracking_url(offer_id.removeprefix("cpalead:"))
    raise CPAError(f"Unknown offer_id format: {offer_id!r}; expected 'network:raw_id'")


def _mylead_tracking_url(raw_id: str) -> str:
    headers = {
        "Authorization": f"Bearer {settings.mylead_api_key}",
        "Accept": "application/json",
    }

    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = _retry(client, "GET", f"{MYLEAD_BASE}/offers/{raw_id}/link", headers=headers)
        if resp.status_code == 404:
            resp = _retry(
                client, "POST", f"{MYLEAD_BASE}/offers/link",
                headers=headers, json={"offer_id": raw_id},
            )
    _raise_for_cpa(resp, f"MyLead get_tracking_url({raw_id})")

    data = resp.json()
    url = data.get("tracking_url") or data.get("url") or data.get("link") or ""
    if not url:
        raise CPAError(f"MyLead get_tracking_url({raw_id}): no URL in response: {data}")

    if "{subid}" not in url and "subid" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}subid={{subid}}"

    return url


def _cpalead_tracking_url(raw_id: str) -> str:
    aff_id = settings.cpalead_affiliate_id
    return f"https://cpalead.com/go.php?o={raw_id}&u={aff_id}&s={{subid}}"
