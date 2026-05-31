"""Anthropic LLM wrapper — always uses the cheap model (Haiku).

Prompt caching is applied to system prompts to avoid redundant token costs
when the same system prompt is reused across calls (e.g., lander generation loop).
"""
from __future__ import annotations

import anthropic

from src.config import settings

_MODEL = "claude-haiku-4-5-20251001"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def complete(system: str, prompt: str, max_tokens: int = 1024) -> str:
    """Call the LLM and return the text response.

    The system prompt is marked for caching so repeated calls with the same
    system prompt hit Anthropic's prompt cache instead of re-tokenizing.
    """
    client = _get_client()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )
    block = response.content[0]
    if block.type != "text":
        raise RuntimeError(f"Unexpected LLM response block type: {block.type}")
    return block.text
