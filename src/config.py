import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load config/.env (the project's canonical env location, where .env.example lives
# and SETUP.md points). Resolve relative to this file so it works from any CWD.
# Fall back to a root .env / default upward search if config/.env is absent.
_ENV_PATH = Path(__file__).resolve().parent.parent / "config" / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
else:
    load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {key}\n"
            f"Copy config/.env.example to config/.env and fill in all required values."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _float(key: str, default: float) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise RuntimeError(f"Environment variable {key} must be a number, got: {raw!r}")


def _int(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"Environment variable {key} must be an integer, got: {raw!r}")


@dataclass
class Settings:
    # Traffic network
    propellerads_api_key: str

    # CPA networks
    mylead_api_key: str
    cpalead_affiliate_id: str

    # LLM (OpenRouter — OpenAI-compatible; model is swappable via LLM_MODEL)
    openrouter_api_key: str
    llm_model: str

    # Notifications
    telegram_bot_token: str
    telegram_chat_id: str

    # Hosting
    domain: str
    dashboard_token: str

    # Budget caps
    global_budget: float
    daily_cap: float

    # Optimizer thresholds
    scale_roi: float
    kill_roi: float
    kill_spend: float
    min_zone_clicks: int
    min_creative_clicks: int
    min_conv: int


def _load() -> Settings:
    # Integration keys are OPTIONAL at boot so the public site (homepage, health,
    # dashboard) always runs. The money-engine activates only once its keys are
    # present — see is_engine_configured(). This decouples "site live" (needed for
    # CPA-network approval) from "all integrations configured".
    return Settings(
        propellerads_api_key=_optional("PROPELLERADS_API_KEY"),
        mylead_api_key=_optional("MYLEAD_API_KEY"),
        cpalead_affiliate_id=_optional("CPALEAD_AFFILIATE_ID"),
        openrouter_api_key=_optional("OPENROUTER_API_KEY"),
        llm_model=_optional("LLM_MODEL", "google/gemini-2.0-flash-001"),
        telegram_bot_token=_optional("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_optional("TELEGRAM_CHAT_ID"),
        domain=_optional("DOMAIN", "http://localhost:8000"),
        dashboard_token=_optional("DASHBOARD_TOKEN"),
        global_budget=_float("GLOBAL_BUDGET", 90.0),
        daily_cap=_float("DAILY_CAP", 10.0),
        scale_roi=_float("SCALE_ROI", 0.20),
        kill_roi=_float("KILL_ROI", -0.50),
        kill_spend=_float("KILL_SPEND", 3.0),
        min_zone_clicks=_int("MIN_ZONE_CLICKS", 50),
        min_creative_clicks=_int("MIN_CREATIVE_CLICKS", 30),
        min_conv=_int("MIN_CONV", 2),
    )


settings = _load()


def has_cpa() -> bool:
    return bool(settings.mylead_api_key or settings.cpalead_affiliate_id)


def is_engine_configured() -> bool:
    """True when the money-engine has the keys it needs to run (traffic + LLM + a
    CPA network). When False, the scheduler jobs idle and the public site still serves.
    """
    return bool(
        settings.propellerads_api_key
        and settings.openrouter_api_key
        and has_cpa()
    )


def missing_engine_keys() -> list[str]:
    """Human-readable list of which keys are still needed to activate the engine."""
    missing = []
    if not settings.propellerads_api_key:
        missing.append("PROPELLERADS_API_KEY")
    if not settings.openrouter_api_key:
        missing.append("OPENROUTER_API_KEY")
    if not has_cpa():
        missing.append("MYLEAD_API_KEY or CPALEAD_AFFILIATE_ID")
    return missing
