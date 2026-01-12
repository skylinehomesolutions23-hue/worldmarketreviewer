import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

# Supabase connection string should be stored in env var DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _require_db_url():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to your environment (Render env vars / local env)."
        )


def _connect():
    _require_db_url()
    # psycopg2 handles sslmode=require in the URL
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """
    Create tables if they don't exist.
    """
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id BIGSERIAL PRIMARY KEY,
        run_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        prob_up DOUBLE PRECISION,
        exp_return DOUBLE PRECISION,
        direction TEXT,
        horizon_days INTEGER DEFAULT 5
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS run_state (
        run_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        total INTEGER NOT NULL,
        completed INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT
    );
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_predictions_run
    ON predictions(run_id);
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_predictions_ticker_time
    ON predictions(ticker, generated_at);
    """)

    conn.commit()
    cur.close()
    conn.close()


# ---------- prediction storage ----------

def insert_predictions(run_id: str, rows: List[Dict[str, Any]]):
    conn = _connect()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    values = []
    for r in rows:
        values.append((
            run_id,
            r.get("ticker"),
            now,
            r.get("prob_up"),
            r.get("exp_return"),
            r.get("direction"),
            int(r.get("horizon_days", 5)),
        ))

    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO predictions
        (run_id, ticker, generated_at, prob_up, exp_return, direction, horizon_days)
        VALUES %s
        """,
        values
    )

    conn.commit()
    cur.close()
    conn.close()


def get_latest_run_id() -> Optional[str]:
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
    SELECT run_id
    FROM predictions
    ORDER BY id DESC
    LIMIT 1
    """)

    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["run_id"] if row else None


def get_predictions_for_run(run_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
    SELECT *
    FROM predictions
    WHERE run_id = %s
    ORDER BY id DESC
    LIMIT %s
    """, (run_id, int(limit)))

    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


# ---------- run state tracking ----------

def create_run(run_id: str, total: int):
    conn = _connect()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    cur.execute("""
    INSERT INTO run_state (run_id, status, total, completed, started_at)
    VALUES (%s, 'running', %s, 0, %s)
    ON CONFLICT (run_id) DO UPDATE SET
      status = EXCLUDED.status,
      total = EXCLUDED.total,
      completed = EXCLUDED.completed,
      started_at = EXCLUDED.started_at,
      finished_at = NULL
    """, (run_id, int(total), now))

    conn.commit()
    cur.close()
    conn.close()


def update_run_progress(run_id: str, completed: int):
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
    UPDATE run_state
    SET completed = %s
    WHERE run_id = %s
    """, (int(completed), run_id))

    conn.commit()
    cur.close()
    conn.close()


def finish_run(run_id: str):
    conn = _connect()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    cur.execute("""
    UPDATE run_state
    SET status = 'finished',
        finished_at = %s
    WHERE run_id = %s
    """, (now, run_id))

    conn.commit()
    cur.close()
    conn.close()


def get_run_state(run_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
    SELECT *
    FROM run_state
    WHERE run_id = %s
    """, (run_id,))

    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None
