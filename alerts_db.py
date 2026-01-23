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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def init_alerts_db() -> Dict[str, Any]:
    """
    Creates the alerts tables if they don't exist.
    Safe to call multiple times.
    """
    url = _db_url()
    if not url:
        return {"ok": True, "skipped": True, "reason": "DATABASE_URL not set"}

    ddl = """
    CREATE TABLE IF NOT EXISTS alert_subscriptions (
        id BIGSERIAL PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        tickers TEXT NOT NULL,                           -- CSV: "SPY,QQQ,NVDA"
        min_prob_up DOUBLE PRECISION NOT NULL DEFAULT 0.65,
        min_confidence TEXT NOT NULL DEFAULT 'MEDIUM',   -- LOW/MEDIUM/HIGH
        horizon_days INTEGER NOT NULL DEFAULT 5,
        source_pref TEXT NOT NULL DEFAULT 'auto',        -- auto/cache/live
        cooldown_minutes INTEGER NOT NULL DEFAULT 360,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_sent_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS alert_events (
        id BIGSERIAL PRIMARY KEY,
        email TEXT NOT NULL,
        ticker TEXT NOT NULL,
        event_type TEXT NOT NULL,                        -- ALERT_TRIGGERED, EMAIL_SENT, EMAIL_SKIPPED, ERROR
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS alert_events_email_created_at
      ON alert_events (email, created_at DESC);

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


def upsert_subscription(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Router passes a dict with keys:
      email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes
    """
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    email = (data.get("email") or "").strip().lower()
    enabled = bool(data.get("enabled", True))
    tickers = (data.get("tickers") or "").strip()
    min_prob_up = float(data.get("min_prob_up", 0.65))
    min_confidence = (data.get("min_confidence") or "MEDIUM").upper().strip()
    horizon_days = int(data.get("horizon_days", 5))
    source_pref = (data.get("source_pref") or "auto").lower().strip()
    cooldown_minutes = int(data.get("cooldown_minutes", 360))

    if not email:
        return {"ok": False, "error": "email required"}
    if not tickers:
        return {"ok": False, "error": "tickers required"}
    if min_confidence not in ("LOW", "MEDIUM", "HIGH"):
        min_confidence = "MEDIUM"
    if source_pref not in ("auto", "cache", "live"):
        source_pref = "auto"

    q = """
    INSERT INTO alert_subscriptions
      (email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes, updated_at)
    VALUES
      (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (email)
    DO UPDATE SET
      enabled = EXCLUDED.enabled,
      tickers = EXCLUDED.tickers,
      min_prob_up = EXCLUDED.min_prob_up,
      min_confidence = EXCLUDED.min_confidence,
      horizon_days = EXCLUDED.horizon_days,
      source_pref = EXCLUDED.source_pref,
      cooldown_minutes = EXCLUDED.cooldown_minutes,
      updated_at = NOW()
    RETURNING id, email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes, last_sent_at, created_at, updated_at;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    q,
                    (
                        email,
                        enabled,
                        tickers,
                        min_prob_up,
                        min_confidence,
                        horizon_days,
                        source_pref,
                        cooldown_minutes,
                    ),
                )
                row = cur.fetchone()
        return dict(row) if row else {}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_subscription(email: str) -> Optional[Dict[str, Any]]:
    url = _db_url()
    if not url:
        return None

    email = (email or "").strip().lower()
    if not email:
        return None

    q = """
    SELECT id, email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes, last_sent_at, created_at, updated_at
    FROM alert_subscriptions
    WHERE email = %s
    LIMIT 1;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (email,))
                row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def list_enabled_subscriptions(limit: int = 200) -> List[Dict[str, Any]]:
    url = _db_url()
    if not url:
        return []

    limit = max(1, min(2000, int(limit)))

    q = """
    SELECT id, email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes, last_sent_at, created_at, updated_at
    FROM alert_subscriptions
    WHERE enabled = TRUE
    ORDER BY updated_at DESC
    LIMIT %s;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (limit,))
                rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []


def set_last_sent_at(email: str, when_iso_utc: str) -> Dict[str, Any]:
    """
    Router calls set_last_sent_at(email, now_iso_string)
    """
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    email = (email or "").strip().lower()
    if not email:
        return {"ok": False, "error": "email required"}

    # Accept ISO string from router, store as timestamptz
    when_dt = None
    try:
        when_dt = datetime.fromisoformat(when_iso_utc.replace("Z", "+00:00"))
    except Exception:
        when_dt = _utcnow()

    q = """
    UPDATE alert_subscriptions
    SET last_sent_at = %s, updated_at = NOW()
    WHERE email = %s
    RETURNING id, email, last_sent_at, updated_at;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (when_dt, email))
                row = cur.fetchone()
        return {"ok": True, "subscription": dict(row) if row else None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def insert_alert_events(email: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Router calls insert_alert_events(email, hits)
    Each hit is expected to contain at least: ticker, prob_up, confidence, as_of_date, source
    We store event_type='ALERT_TRIGGERED' with payload=hit.
    """
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    email = (email or "").strip().lower()
    if not email:
        return {"ok": False, "error": "email required"}

    rows = []
    for h in hits or []:
        ticker = (h.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        rows.append((email, ticker, "ALERT_TRIGGERED", json.dumps(h)))

    if not rows:
        return {"ok": True, "inserted": 0}

    q = """
    INSERT INTO alert_events (email, ticker, event_type, payload)
    VALUES (%s, %s, %s, %s::jsonb);
    """

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, q, rows, page_size=200)
        return {"ok": True, "inserted": len(rows)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_alert_events(email: str, limit: int = 200) -> List[Dict[str, Any]]:
    url = _db_url()
    if not url:
        return []

    email = (email or "").strip().lower()
    if not email:
        return []

    limit = max(1, min(2000, int(limit)))

    q = """
    SELECT id, email, ticker, event_type, payload, created_at
    FROM alert_events
    WHERE email = %s
    ORDER BY created_at DESC
    LIMIT %s;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (email, limit))
                rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []
