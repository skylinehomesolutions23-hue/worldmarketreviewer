import sqlite3
from pathlib import Path
import json

# -----------------------------
# Paths
# -----------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "history.db"
SUMMARY_PATH = DATA_DIR / "latest_summary.json"


# -----------------------------
# Connection
# -----------------------------

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# -----------------------------
# Init DB
# -----------------------------

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
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


init_db()


# -----------------------------
# History functions (tracker.py)
# -----------------------------

def insert_row(timestamp, status, exposure, vol, drawdown):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO history (timestamp, status, exposure, vol, drawdown)
            VALUES (?, ?, ?, ?, ?)
        """, (timestamp, status, exposure, vol, drawdown))
        conn.commit()


def fetch_recent(limit=200):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, status, exposure, vol, drawdown
            FROM history
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()

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


# -----------------------------
# Summary functions (build_mobile_summary.py)
# -----------------------------

def save_summary(summary: dict):
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2)


def load_summary():
    if not SUMMARY_PATH.exists():
        return None

    with open(SUMMARY_PATH, "r") as f:
        return json.load(f)
