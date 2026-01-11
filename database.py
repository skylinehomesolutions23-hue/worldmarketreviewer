# database.py

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "history.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            status TEXT,
            exposure REAL,
            vol REAL,
            drawdown REAL
        )
    """)

    conn.commit()
    conn.close()


def insert_row(timestamp, status, exposure, vol, drawdown):
    init_db()  # <-- ensures table always exists

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        INSERT INTO history (timestamp, status, exposure, vol, drawdown)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, status, exposure, vol, drawdown))

    conn.commit()
    conn.close()


def fetch_recent(limit=200):
    init_db()

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT timestamp, status, exposure, vol, drawdown
        FROM history
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = c.fetchall()
    conn.close()

    return [
        {
            "timestamp": r[0],
            "status": r[1],
            "exposure": r[2],
            "vol": r[3],
            "drawdown": r[4],
        }
        for r in rows
    ]
