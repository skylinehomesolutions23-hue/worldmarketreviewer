# database.py

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        cur = conn.cursor()

        # Stores latest summary only
        cur.execute("""
        CREATE TABLE IF NOT EXISTS summary (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            timestamp TEXT,
            status TEXT,
            recommended_exposure REAL,
            rolling_net_return REAL,
            vol_3m REAL,
            max_drawdown_3m REAL,
            tail_correlation REAL,
            kill_signal INTEGER,
            reason TEXT,
            profile TEXT
        )
        """)

        # Stores historical snapshots
        cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT UNIQUE,
            exposure REAL,
            status TEXT
        )
        """)

        conn.commit()


def save_summary(data: dict):
    init_db()
    now = datetime.utcnow().isoformat()

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO summary (
            id, timestamp, status, recommended_exposure, rolling_net_return,
            vol_3m, max_drawdown_3m, tail_correlation,
            kill_signal, reason, profile
        ) VALUES (
            1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(id) DO UPDATE SET
            timestamp = excluded.timestamp,
            status = excluded.status,
            recommended_exposure = excluded.recommended_exposure,
            rolling_net_return = excluded.rolling_net_return,
            vol_3m = excluded.vol_3m,
            max_drawdown_3m = excluded.max_drawdown_3m,
            tail_correlation = excluded.tail_correlation,
            kill_signal = excluded.kill_signal,
            reason = excluded.reason,
            profile = excluded.profile
        """, (
            now,
            data["status"],
            data["recommended_exposure"],
            data["rolling_net_return"],
            data["vol_3m"],
            data["max_drawdown_3m"],
            data["tail_correlation"],
            int(data["kill_signal"]),
            data["reason"],
            data["profile"]
        ))

        conn.commit()


def save_history(timestamp: str, exposure: float, status: str):
    init_db()

    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO history (timestamp, exposure, status)
                VALUES (?, ?, ?)
            """, (timestamp, exposure, status))
            conn.commit()
        except sqlite3.IntegrityError:
            # duplicate timestamp → ignore safely
            pass


def get_latest_summary():
    init_db()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM summary WHERE id = 1")
        row = cur.fetchone()

    if not row:
        return {}

    keys = [
        "id", "timestamp", "status", "recommended_exposure",
        "rolling_net_return", "vol_3m", "max_drawdown_3m",
        "tail_correlation", "kill_signal", "reason", "profile"
    ]

    return dict(zip(keys, row))


def get_history(limit=100):
    init_db()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp, exposure, status
            FROM history
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()

    return [
        {"timestamp": r[0], "exposure": r[1], "status": r[2]}
        for r in rows
    ]
