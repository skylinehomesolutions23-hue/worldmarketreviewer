# alerts_db.py (PART 1/2)
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


def _db_url() -> Optional[str]:
    return os.getenv("DATABASE_URL")


def _connect():
    url = _db_url()
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    # Supabase commonly needs SSL
    return psycopg2.connect(url, sslmode=os.getenv("PGSSLMODE", "require"))


def init_alerts_db() -> Dict[str, Any]:
    """
    Creates the alerts tables if they don't exist.
    Safe to call multiple times.
    """
    url = _db_url()
    if not url:
        # Local dev: don't crash your whole API just because DB isn't configured
        return {"ok": True, "skipped": True, "reason": "DATABASE_URL not set"}

    ddl = """
    CREATE TABLE IF NOT EXISTS alert_subscriptions (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT 'demo',
        ticker TEXT NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        direction TEXT NOT NULL DEFAULT 'UP',            -- UP or DOWN
        threshold_prob DOUBLE PRECISION NOT NULL DEFAULT 0.65,
        language TEXT NOT NULL DEFAULT 'English',
        country TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_sent_at TIMESTAMPTZ
    );

    CREATE UNIQUE INDEX IF NOT EXISTS alert_subscriptions_unique
      ON alert_subscriptions (user_id, ticker);

    CREATE TABLE IF NOT EXISTS alert_events (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT 'demo',
        ticker TEXT NOT NULL,
        event_type TEXT NOT NULL,                       -- 'ALERT_SENT', 'ALERT_SKIPPED', etc.
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS alert_events_ticker_created_at
      ON alert_events (ticker, created_at DESC);
    """

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
        return {"ok": True, "skipped": False}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _utcnow():
    return datetime.now(timezone.utc)


def upsert_subscription(
    user_id: str,
    ticker: str,
    enabled: bool = True,
    direction: str = "UP",
    threshold_prob: float = 0.65,
    language: str = "English",
    country: Optional[str] = None,
) -> Dict[str, Any]:
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    user_id = (user_id or "demo").strip() or "demo"
    ticker = (ticker or "").upper().strip()
    direction = (direction or "UP").upper().strip()
    language = (language or "English").strip() or "English"
    country = (country or None)

    if not ticker:
        return {"ok": False, "error": "ticker required"}
    if direction not in ("UP", "DOWN"):
        direction = "UP"

    q = """
    INSERT INTO alert_subscriptions (user_id, ticker, enabled, direction, threshold_prob, language, country, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (user_id, ticker)
    DO UPDATE SET
      enabled = EXCLUDED.enabled,
      direction = EXCLUDED.direction,
      threshold_prob = EXCLUDED.threshold_prob,
      language = EXCLUDED.language,
      country = EXCLUDED.country,
      updated_at = NOW()
    RETURNING id, user_id, ticker, enabled, direction, threshold_prob, language, country, last_sent_at, updated_at;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (user_id, ticker, bool(enabled), direction, float(threshold_prob), language, country))
                row = cur.fetchone()
        return {"ok": True, "subscription": dict(row) if row else None}
    except Exception as e:
        return {"ok": False, "error": str(e)}
# alerts_db.py (PART 2/2)

def get_subscription(user_id: str, ticker: str) -> Optional[Dict[str, Any]]:
    url = _db_url()
    if not url:
        return None

    user_id = (user_id or "demo").strip() or "demo"
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return None

    q = """
    SELECT id, user_id, ticker, enabled, direction, threshold_prob, language, country, last_sent_at, created_at, updated_at
    FROM alert_subscriptions
    WHERE user_id = %s AND ticker = %s
    LIMIT 1;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (user_id, ticker))
                row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def list_enabled_subscriptions(user_id: str = "demo", limit: int = 200) -> List[Dict[str, Any]]:
    url = _db_url()
    if not url:
        return []

    user_id = (user_id or "demo").strip() or "demo"
    limit = max(1, min(2000, int(limit)))

    q = """
    SELECT id, user_id, ticker, enabled, direction, threshold_prob, language, country, last_sent_at, created_at, updated_at
    FROM alert_subscriptions
    WHERE user_id = %s AND enabled = TRUE
    ORDER BY updated_at DESC
    LIMIT %s;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (user_id, limit))
                rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []


def set_last_sent_at(user_id: str, ticker: str, when_utc: Optional[datetime] = None) -> Dict[str, Any]:
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    user_id = (user_id or "demo").strip() or "demo"
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return {"ok": False, "error": "ticker required"}

    when_utc = when_utc or _utcnow()

    q = """
    UPDATE alert_subscriptions
    SET last_sent_at = %s, updated_at = NOW()
    WHERE user_id = %s AND ticker = %s
    RETURNING id, user_id, ticker, last_sent_at, updated_at;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (when_utc, user_id, ticker))
                row = cur.fetchone()
        return {"ok": True, "subscription": dict(row) if row else None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def insert_alert_events(
    events: List[Dict[str, Any]],
    user_id: str = "demo",
) -> Dict[str, Any]:
    """
    Insert multiple alert_events rows.
    Each event dict should include: ticker, event_type, payload (optional)
    """
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    user_id = (user_id or "demo").strip() or "demo"
    rows = []
    for e in events or []:
        ticker = (e.get("ticker") or "").upper().strip()
        event_type = (e.get("event_type") or "").strip()
        payload = e.get("payload") or {}
        if not ticker or not event_type:
            continue
        rows.append((user_id, ticker, event_type, json.dumps(payload)))

    if not rows:
        return {"ok": True, "inserted": 0}

    q = """
    INSERT INTO alert_events (user_id, ticker, event_type, payload)
    VALUES (%s, %s, %s, %s::jsonb);
    """

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, q, rows, page_size=200)
        return {"ok": True, "inserted": len(rows)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_alert_events(
    user_id: str = "demo",
    ticker: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    url = _db_url()
    if not url:
        return []

    user_id = (user_id or "demo").strip() or "demo"
    limit = max(1, min(2000, int(limit)))
    ticker = (ticker or "").upper().strip() if ticker else None

    if ticker:
        q = """
        SELECT id, user_id, ticker, event_type, payload, created_at
        FROM alert_events
        WHERE user_id = %s AND ticker = %s
        ORDER BY created_at DESC
        LIMIT %s;
        """
        params = (user_id, ticker, limit)
    else:
        q = """
        SELECT id, user_id, ticker, event_type, payload, created_at
        FROM alert_events
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s;
        """
        params = (user_id, limit)

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, params)
                rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []
