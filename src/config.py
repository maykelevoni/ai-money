import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

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

    # LLM
    anthropic_api_key: str

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
    # At least one CPA network key must be present; both are optional individually
    # but we need one to fetch offers.
    mylead = _optional("MYLEAD_API_KEY")
    cpalead = _optional("CPALEAD_AFFILIATE_ID")
    if not mylead and not cpalead:
        raise RuntimeError(
            "Missing CPA network credentials: set at least one of "
            "MYLEAD_API_KEY or CPALEAD_AFFILIATE_ID in your .env file."
        )

    return Settings(
        propellerads_api_key=_require("PROPELLERADS_API_KEY"),
        mylead_api_key=mylead,
        cpalead_affiliate_id=cpalead,
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_require("TELEGRAM_CHAT_ID"),
        domain=_require("DOMAIN"),
        dashboard_token=_require("DASHBOARD_TOKEN"),
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
