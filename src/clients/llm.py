"""LLM wrapper — OpenRouter (OpenAI-compatible chat completions).

The model is configured via the LLM_MODEL env var, so swapping models is a
one-line .env change with no code edits. Uses httpx directly (no extra SDK).
"""
from __future__ import annotations

import httpx

from src.config import settings

_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = httpx.Timeout(60.0)

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=_TIMEOUT,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                # Optional attribution headers OpenRouter recommends:
                "HTTP-Referer": settings.domain,
                "X-Title": "ai-money autonomous engine",
            },
        )
    return _client


def complete(system: str, prompt: str, max_tokens: int = 1024) -> str:
    """Call the configured OpenRouter model and return the text response.

    Model comes from settings.llm_model (LLM_MODEL env var) — easy to swap.
    """
    client = _get_client()
    resp = client.post(
        _BASE_URL,
        json={
            "model": settings.llm_model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"OpenRouter request failed ({resp.status_code}): {resp.text[:300]}"
        )
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter response shape: {data}") from exc
