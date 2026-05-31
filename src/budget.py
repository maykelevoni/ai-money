from src.config import settings
from src.db import execute, fetchone


def _last_running_total() -> float:
    row = fetchone("SELECT running_total FROM budget_ledger ORDER BY id DESC LIMIT 1")
    return float(row["running_total"]) if row else 0.0


def _total_spent() -> float:
    row = fetchone(
        "SELECT COALESCE(SUM(amount), 0.0) AS total FROM budget_ledger WHERE kind = 'spend'"
    )
    return float(row["total"]) if row else 0.0


def record_deposit(amount: float) -> None:
    new_total = _last_running_total() + amount
    execute(
        "INSERT INTO budget_ledger (amount, kind, running_total) VALUES (?, 'deposit', ?)",
        (amount, new_total),
    )


def record_spend(amount: float) -> None:
    new_total = _last_running_total() - amount
    execute(
        "INSERT INTO budget_ledger (amount, kind, running_total) VALUES (?, 'spend', ?)",
        (amount, new_total),
    )


def remaining_global() -> float:
    return settings.global_budget - _total_spent()


def spent_today() -> float:
    row = fetchone(
        "SELECT COALESCE(SUM(amount), 0.0) AS total "
        "FROM budget_ledger "
        "WHERE kind = 'spend' AND date(ts) = date('now')"
    )
    return float(row["total"]) if row else 0.0


def can_spend(amount: float) -> bool:
    if _total_spent() + amount > settings.global_budget:
        return False
    if spent_today() + amount > settings.daily_cap:
        return False
    return True


def is_global_exhausted() -> bool:
    return remaining_global() <= 0.0


def is_daily_exhausted() -> bool:
    return spent_today() >= settings.daily_cap
