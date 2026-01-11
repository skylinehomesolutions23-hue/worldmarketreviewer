# database.py

import sqlite3
from settings import DB_FILE

def init_db():
    conn = sqlite3.connect(DB_FILE)
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
    INSERT INTO history (timestamp, status, exposure, vol, drawdown)
    VALUES (?, ?, ?, ?, ?)
    """, (timestamp, status, exposure, vol, drawdown))

    conn.commit()
    conn.close()


def fetch_recent(limit=200):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    rows = c.execute("""
    SELECT timestamp, status, exposure, vol, drawdown
    FROM history
    ORDER BY id DESC
    LIMIT ?
    """, (limit,)).fetchall()

    conn.close()

    return [
        {
            "timestamp": r[0],
            "status": r[1],
            "exposure": r[2],
            "vol": r[3],
            "drawdown": r[4],
        }
        for r in reversed(rows)
    ]
