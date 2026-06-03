"""Digistore24 classic API client — thin, typed, no business logic."""
from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import httpx

from src.config import settings

BASE = "https://www.digistore24.com/api/call"
_PROMOLINK_BASE = "https://www.digistore24.com/redir"

_TIMEOUT = httpx.Timeout(15.0)
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


# ── Typed errors ──────────────────────────────────────────────────────────────

class Digistore24Error(Exception):
    pass


class Digistore24AuthError(Digistore24Error):
    pass


# ── Internal helpers ──────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    return {
        "X-DS-API-KEY": settings.digistore24_api_key,
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


def _raise_for_auth(resp: httpx.Response, context: str) -> None:
    if resp.status_code == 401:
        raise Digistore24AuthError(f"{context}: 401 Unauthorized — check API key")
    if not resp.is_success:
        raise Digistore24Error(f"{context}: HTTP {resp.status_code} — {resp.text[:300]}")


# ── Public API ────────────────────────────────────────────────────────────────

_NUMERIC_ID_RE = re.compile(r"^\d+$")
_REDIR_RE = re.compile(r"/redir/(\d+)")


def parse_product_id(line: str) -> str | None:
    """Extract a Digistore24 numeric product id from a line of user input.

    Accepts bare numeric ids, redir/promolinks, and marketplace URLs.
    Returns None for blank or unrecognisable input.
    """
    line = line.strip()
    if not line:
        return None

    if _NUMERIC_ID_RE.match(line):
        return line

    m = _REDIR_RE.search(line)
    if m:
        return m.group(1)

    # fallback: first 5+-digit path segment (avoids port numbers / short ids)
    parsed = urlparse(line)
    for segment in parsed.path.split("/"):
        if _NUMERIC_ID_RE.match(segment) and len(segment) >= 5:
            return segment

    return None


def get_user_info() -> dict:
    """GET getUserInfo; return the data dict (includes user_name)."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = _retry(client, "GET", f"{BASE}/getUserInfo", headers=_headers())
    _raise_for_auth(resp, "getUserInfo")
    payload = resp.json()
    if payload.get("result") != "success":
        raise Digistore24Error(f"getUserInfo: {payload.get('message', payload)}")
    return payload.get("data", {})


def resolve_affiliate_name() -> str:
    """Return configured affiliate name, falling back to getUserInfo."""
    name = settings.digistore24_affiliate_name
    if name:
        return name
    return get_user_info().get("user_name", "")


def get_marketplace_entry(entry_id: str) -> dict | None:
    """GET getMarketplaceEntry; returns the data dict or None on any failure.

    Best-effort: never raises for missing/inaccessible entries.
    """
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = _retry(
                client, "GET", f"{BASE}/getMarketplaceEntry",
                headers=_headers(), params={"entry_id": entry_id},
            )
        if resp.status_code in (403, 404):
            return None
        if not resp.is_success:
            return None
        payload = resp.json()
        if payload.get("result") != "success":
            return None
        return payload.get("data") or None
    except Exception:
        return None


def build_promolink(product_id: str, affiliate_name: str, campaign_key: str = "") -> str:
    """Build the Digistore24 affiliate promolink.

    Format: https://www.digistore24.com/redir/{product_id}/{affiliate_name}/{campaign_key}
    The campaign_key segment is omitted when empty.
    """
    if campaign_key:
        return f"{_PROMOLINK_BASE}/{product_id}/{affiliate_name}/{campaign_key}"
    return f"{_PROMOLINK_BASE}/{product_id}/{affiliate_name}"
