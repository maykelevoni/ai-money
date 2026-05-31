import sqlite3
import threading
from pathlib import Path

DB_PATH = Path("data/engine.db")

_local = threading.local()


def _conn() -> sqlite3.Connection:
    if not getattr(_local, "conn", None):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


def init_db() -> None:
    schema = (Path(__file__).parent / "schema.sql").read_text()
    conn = _conn()
    conn.executescript(schema)
    conn.commit()


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    conn = _conn()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur


def fetchone(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    return _conn().execute(sql, params).fetchone()


def fetchall(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return _conn().execute(sql, params).fetchall()
