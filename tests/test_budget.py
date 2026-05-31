import os

# Set dummy env vars before any src import triggers config._load()
for _key, _val in {
    "PROPELLERADS_API_KEY": "test-key",
    "ANTHROPIC_API_KEY": "test-key",
    "TELEGRAM_BOT_TOKEN": "test-token",
    "TELEGRAM_CHAT_ID": "test-chat",
    "DOMAIN": "test.example.com",
    "DASHBOARD_TOKEN": "test-token",
    "MYLEAD_API_KEY": "test-key",
}.items():
    os.environ.setdefault(_key, _val)

import pytest
from unittest.mock import patch

import src.db as db
import src.budget as budget
from src.config import Settings


def _cfg(**overrides) -> Settings:
    base = dict(
        propellerads_api_key="test",
        mylead_api_key="test",
        cpalead_affiliate_id="",
        anthropic_api_key="test",
        telegram_bot_token="test",
        telegram_chat_id="test",
        domain="test.example.com",
        dashboard_token="test",
        global_budget=100.0,
        daily_cap=20.0,
        scale_roi=0.20,
        kill_roi=-0.50,
        kill_spend=3.0,
        min_zone_clicks=50,
        min_creative_clicks=30,
        min_conv=2,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    conn = getattr(db._local, "conn", None)
    if conn:
        conn.close()
    db._local.conn = None
    db.init_db()
    yield
    conn = getattr(db._local, "conn", None)
    if conn:
        conn.close()
    db._local.conn = None


def test_spend_cannot_exceed_global_budget():
    cfg = _cfg(global_budget=50.0, daily_cap=500.0)
    with patch("src.budget.settings", cfg):
        budget.record_deposit(50.0)
        assert budget.can_spend(30.0) is True
        budget.record_spend(30.0)
        assert budget.can_spend(20.0) is True
        budget.record_spend(20.0)
        # Total spent = 50.0 == global_budget; one more cent is blocked
        assert budget.can_spend(0.01) is False
        assert budget.is_global_exhausted() is True


def test_daily_cap_blocks_spend_and_exhausted_flag():
    cfg = _cfg(global_budget=500.0, daily_cap=15.0)
    with patch("src.budget.settings", cfg):
        budget.record_deposit(500.0)
        assert budget.can_spend(10.0) is True
        budget.record_spend(10.0)
        assert budget.can_spend(5.0) is True
        budget.record_spend(5.0)
        # spent_today = 15.0 == daily_cap; one more cent is blocked
        assert budget.can_spend(0.01) is False
        assert budget.is_daily_exhausted() is True
        # Global is not exhausted
        assert budget.is_global_exhausted() is False


def test_daily_cap_resets_for_new_day():
    cfg = _cfg(global_budget=500.0, daily_cap=15.0)
    with patch("src.budget.settings", cfg):
        # Insert a spend row timestamped yesterday
        db.execute(
            "INSERT INTO budget_ledger (ts, amount, kind, running_total) VALUES (?, ?, 'spend', ?)",
            ("2000-01-01 12:00:00", 14.0, -14.0),
        )
        # Today's spend should be zero — yesterday's rows are not counted
        assert budget.spent_today() == pytest.approx(0.0)
        assert budget.can_spend(15.0) is True
        budget.record_spend(15.0)
        assert budget.is_daily_exhausted() is True


def test_remaining_and_spent_today_with_mixed_rows():
    cfg = _cfg(global_budget=100.0, daily_cap=50.0)
    with patch("src.budget.settings", cfg):
        budget.record_deposit(80.0)
        budget.record_spend(12.0)
        budget.record_deposit(20.0)  # another deposit; should not count as spend
        budget.record_spend(5.0)
        assert budget.remaining_global() == pytest.approx(83.0)  # 100 - (12+5)
        assert budget.spent_today() == pytest.approx(17.0)        # 12 + 5
        assert budget.is_global_exhausted() is False
        assert budget.is_daily_exhausted() is False


def test_running_total_tracks_net_balance():
    cfg = _cfg(global_budget=200.0, daily_cap=200.0)
    with patch("src.budget.settings", cfg):
        budget.record_deposit(100.0)   # running_total = 100
        budget.record_spend(30.0)      # running_total = 70
        budget.record_deposit(50.0)    # running_total = 120
        budget.record_spend(20.0)      # running_total = 100
        row = db.fetchone(
            "SELECT running_total FROM budget_ledger ORDER BY id DESC LIMIT 1"
        )
        assert float(row["running_total"]) == pytest.approx(100.0)
