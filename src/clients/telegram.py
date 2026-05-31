"""Telegram Bot API wrapper — delivers notifications to the configured chat.

Fails soft: logs a warning and returns without raising so a Telegram outage
never crashes the engine.
"""
from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0)


def send(text: str) -> None:
    """Send a Markdown message to the configured Telegram chat.

    Silently logs on failure — never raises.
    """
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    try:
        response = httpx.post(url, json=payload, timeout=_TIMEOUT)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Telegram send failed (message dropped): %s", exc)
