import os

# Minimal env vars so src.config loads without errors in tests.
# These are fake test values — no real credentials.
_TEST_DEFAULTS = {
    "PROPELLERADS_API_KEY": "test-key",
    "MYLEAD_API_KEY": "test-key",
    "ANTHROPIC_API_KEY": "test-key",
    "TELEGRAM_BOT_TOKEN": "test-token",
    "TELEGRAM_CHAT_ID": "99999",
    "DOMAIN": "test.example.com",
    "DASHBOARD_TOKEN": "test-dashboard-token",
}

for _k, _v in _TEST_DEFAULTS.items():
    os.environ.setdefault(_k, _v)
