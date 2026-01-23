import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


def _db_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()


def _require_db_url():
    if not _db_url():
        raise RuntimeError("DATABASE_URL is not set. Add it to your environment.")


def _connect():
    _require_db_url()
    return psycopg2.connect(_db_url())


def init_alerts_db():
    """
    Creates the alerts table if missing.
    """
    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts_subscriptions (
          id BIGSERIAL PRIMARY KEY,
          email TEXT NOT NULL,
          tickers TEXT NOT NULL,         -- comma-separated tickers
          horizon_days INTEGER DEFAULT 5,
          min_confidence TEXT DEFAULT 'MEDIUM',
          created_at TEXT NOT NULL,
          last_sent_at TEXT
        );
        """
    )

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_alerts_email ON alerts_subscriptions(email);"
    )

    conn.commit()
    cur.close()
    conn.close()


def add_subscription(
    email: str,
    tickers_csv: str,
    horizon_days: int,
    min_confidence: str,
) -> Dict[str, Any]:
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    cur.execute(
        """
        INSERT INTO alerts_subscriptions (email, tickers, horizon_days, min_confidence, created_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (email.strip().lower(), tickers_csv, int(horizon_days), (min_confidence or "MEDIUM").upper().strip(), now),
    )
    row = cur.fetchone()

    conn.commit()
    cur.close()
    conn.close()
    return dict(row) if row else {}


def list_subscriptions(limit: int = 200) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT *
        FROM alerts_subscriptions
        ORDER BY id DESC
        LIMIT %s
        """,
        (int(limit),),
    )
    rows = [dict(r) for r in cur.fetchall()]

    cur.close()
    conn.close()
    return rows


def delete_subscription(sub_id: int) -> bool:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM alerts_subscriptions WHERE id = %s", (int(sub_id),))
    deleted = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return deleted


def mark_sent(sub_id: int):
    conn = _connect()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    cur.execute(
        """
        UPDATE alerts_subscriptions
        SET last_sent_at = %s
        WHERE id = %s
        """,
        (now, int(sub_id)),
    )
    conn.commit()
    cur.close()
    conn.close()
