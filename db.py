# db.py
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "app.db")

def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        prob_up REAL,
        exp_return REAL,
        direction TEXT,
        horizon_days INTEGER DEFAULT 5
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_predictions_run
    ON predictions(run_id)
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_predictions_ticker_time
    ON predictions(ticker, generated_at)
    """)

    conn.commit()
    conn.close()


def insert_predictions(run_id: str, rows: List[Dict[str, Any]]):
    conn = _connect()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    for r in rows:
        cur.execute("""
        INSERT INTO predictions (run_id, ticker, generated_at, prob_up, exp_return, direction, horizon_days)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            r.get("ticker"),
            now,
            r.get("prob_up"),
            r.get("exp_return"),
            r.get("direction"),
            r.get("horizon_days", 5),
        ))

    conn.commit()
    conn.close()


def get_latest_predictions(limit: int = 50) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM predictions
    ORDER BY id DESC
    LIMIT ?
    """, (limit,))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_latest_run_id() -> Optional[str]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT run_id FROM predictions ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row["run_id"] if row else None


def get_predictions_for_run(run_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM predictions
    WHERE run_id = ?
    ORDER BY id DESC
    LIMIT ?
    """, (run_id, limit))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
