import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load config/.env if present (local dev); otherwise rely on real env vars / DB.
_ENV_PATH = Path(__file__).resolve().parent.parent / "config" / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
else:
    load_dotenv()


# ---------------------------------------------------------------------------
# Value resolution: DB settings table  ->  environment variable  ->  default.
# This lets every key be managed from the dashboard Settings page (stored in
# the DB) with no env vars and no redeploy required.
# ---------------------------------------------------------------------------
def _db_get(key: str):
    try:
        from src import db
        row = db.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else None
    except Exception:
        return None


def _resolve(key: str, default: str = "") -> str:
    val = _db_get(key)
    if val is not None and val.strip() != "":
        return val.strip()
    env = os.getenv(key, "")
    if env.strip() != "":
        return env.strip()
    return default


def _resolve_float(key: str, default: float) -> float:
    raw = _resolve(key, "")
    try:
        return float(raw) if raw != "" else default
    except ValueError:
        return default


def _resolve_int(key: str, default: int) -> int:
    raw = _resolve(key, "")
    try:
        return int(raw) if raw != "" else default
    except ValueError:
        return default


@dataclass
class Settings:
    """Frozen config snapshot — used by tests. Runtime uses the live object below."""
    propellerads_api_key: str
    mylead_api_key: str
    cpalead_affiliate_id: str
    openrouter_api_key: str
    llm_model: str
    telegram_bot_token: str
    telegram_chat_id: str
    domain: str
    dashboard_token: str
    global_budget: float
    daily_cap: float
    scale_roi: float
    kill_roi: float
    kill_spend: float
    min_zone_clicks: int
    min_creative_clicks: int
    min_conv: int


class _LiveSettings:
    """Each attribute resolves DB -> env -> default at access time, so values
    saved on the dashboard Settings page take effect immediately."""

    @property
    def propellerads_api_key(self) -> str:
        return _resolve("PROPELLERADS_API_KEY")

    @property
    def mylead_api_key(self) -> str:
        return _resolve("MYLEAD_API_KEY")

    @property
    def cpalead_affiliate_id(self) -> str:
        return _resolve("CPALEAD_AFFILIATE_ID")

    @property
    def openrouter_api_key(self) -> str:
        return _resolve("OPENROUTER_API_KEY")

    @property
    def llm_model(self) -> str:
        return _resolve("LLM_MODEL", "google/gemini-2.0-flash-001")

    @property
    def telegram_bot_token(self) -> str:
        return _resolve("TELEGRAM_BOT_TOKEN")

    @property
    def telegram_chat_id(self) -> str:
        return _resolve("TELEGRAM_CHAT_ID")

    @property
    def domain(self) -> str:
        return _resolve("DOMAIN", "http://localhost:8000")

    @property
    def dashboard_token(self) -> str:
        return _resolve("DASHBOARD_TOKEN")

    @property
    def global_budget(self) -> float:
        return _resolve_float("GLOBAL_BUDGET", 90.0)

    @property
    def daily_cap(self) -> float:
        return _resolve_float("DAILY_CAP", 10.0)

    @property
    def scale_roi(self) -> float:
        return _resolve_float("SCALE_ROI", 0.20)

    @property
    def kill_roi(self) -> float:
        return _resolve_float("KILL_ROI", -0.50)

    @property
    def kill_spend(self) -> float:
        return _resolve_float("KILL_SPEND", 3.0)

    @property
    def min_zone_clicks(self) -> int:
        return _resolve_int("MIN_ZONE_CLICKS", 50)

    @property
    def min_creative_clicks(self) -> int:
        return _resolve_int("MIN_CREATIVE_CLICKS", 30)

    @property
    def min_conv(self) -> int:
        return _resolve_int("MIN_CONV", 2)

    @property
    def digistore24_api_key(self) -> str:
        val = _resolve("DIGISTORE24_API_KEY")
        if val:
            return val
        return os.getenv("DIGISTORE", "")

    @property
    def digistore24_affiliate_name(self) -> str:
        return _resolve("DIGISTORE24_AFFILIATE_NAME", "")

    @property
    def digistore24_min_commission(self) -> float:
        return _resolve_float("DIGISTORE24_MIN_COMMISSION", 50.0)

    @property
    def digistore24_max_cancel_rate(self) -> float:
        return _resolve_float("DIGISTORE24_MAX_CANCEL_RATE", 15.0)


settings = _LiveSettings()


# ---------------------------------------------------------------------------
# Settings managed from the dashboard. (key, label, kind, secret)
# ---------------------------------------------------------------------------
MANAGED_SETTINGS = [
    ("PROPELLERADS_API_KEY", "PropellerAds API key", "password", True),
    ("OPENROUTER_API_KEY", "OpenRouter API key", "password", True),
    ("LLM_MODEL", "LLM model (OpenRouter id)", "text", False),
    ("MYLEAD_API_KEY", "MyLead API key", "password", True),
    ("CPALEAD_AFFILIATE_ID", "CPALead affiliate ID (fallback)", "text", False),
    ("TELEGRAM_BOT_TOKEN", "Telegram bot token", "password", True),
    ("TELEGRAM_CHAT_ID", "Telegram chat ID", "text", False),
    ("DOMAIN", "Public domain (https://...)", "text", False),
    ("GLOBAL_BUDGET", "Global budget cap (USD)", "number", False),
    ("DAILY_CAP", "Daily spend cap (USD)", "number", False),
    ("SCALE_ROI", "Scale-winner ROI threshold (e.g. 0.20)", "number", False),
    ("KILL_ROI", "Kill-loser ROI threshold (e.g. -0.50)", "number", False),
    ("KILL_SPEND", "Min spend before kill (USD)", "number", False),
    ("MIN_ZONE_CLICKS", "Min zone clicks before blacklist", "number", False),
    ("MIN_CREATIVE_CLICKS", "Min creative clicks before pause", "number", False),
    ("MIN_CONV", "Min conversions before scaling", "number", False),
    ("DIGISTORE24_API_KEY", "Digistore24 API key", "password", True),
    ("DIGISTORE24_AFFILIATE_NAME", "Digistore24 affiliate name", "text", False),
    ("DIGISTORE24_MIN_COMMISSION", "Digistore24 min commission % (e.g. 50)", "number", False),
    ("DIGISTORE24_MAX_CANCEL_RATE", "Digistore24 max cancel rate % (e.g. 15)", "number", False),
]


def get_setting_value(key: str, default: str = "") -> str:
    return _resolve(key, default)


def set_setting(key: str, value: str) -> None:
    from src import db
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def has_digistore() -> bool:
    return bool(settings.digistore24_api_key)


def has_cpa() -> bool:
    return bool(settings.mylead_api_key or settings.cpalead_affiliate_id)


def is_engine_configured() -> bool:
    """True when the engine has traffic + LLM + a CPA network configured."""
    return bool(settings.propellerads_api_key and settings.openrouter_api_key and has_cpa())


def missing_engine_keys() -> list[str]:
    missing = []
    if not settings.propellerads_api_key:
        missing.append("PROPELLERADS_API_KEY")
    if not settings.openrouter_api_key:
        missing.append("OPENROUTER_API_KEY")
    if not has_cpa():
        missing.append("MYLEAD_API_KEY or CPALEAD_AFFILIATE_ID")
    return missing
