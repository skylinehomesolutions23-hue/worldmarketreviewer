# alerts_db.py
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras


def _db_url() -> Optional[str]:
    return os.getenv("DATABASE_URL")


def _connect():
    url = _db_url()
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(url, sslmode=os.getenv("PGSSLMODE", "require"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def init_alerts_db() -> Dict[str, Any]:
    """
    Creates/updates the alerts tables if they don't exist.
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
        event_type TEXT NOT NULL,                        -- ALERT_TRIGGERED, EMAIL_SENT, EMAIL_SKIPPED, ERROR, RECAP_SENT
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS alert_events_email_created_at
      ON alert_events (email, created_at DESC);

    CREATE INDEX IF NOT EXISTS alert_events_ticker_created_at
      ON alert_events (ticker, created_at DESC);

    -- Helpful for per-ticker cooldown lookups:
    CREATE INDEX IF NOT EXISTS alert_events_email_ticker_type_created_at
      ON alert_events (email, ticker, event_type, created_at DESC);
    """

    # Add recap columns if missing (no migration tool needed)
    alter = """
    ALTER TABLE alert_subscriptions
      ADD COLUMN IF NOT EXISTS recap_enabled BOOLEAN NOT NULL DEFAULT FALSE;

    ALTER TABLE alert_subscriptions
      ADD COLUMN IF NOT EXISTS recap_time_local TEXT NOT NULL DEFAULT '21:00';

    ALTER TABLE alert_subscriptions
      ADD COLUMN IF NOT EXISTS recap_timezone TEXT NOT NULL DEFAULT 'America/New_York';

    ALTER TABLE alert_subscriptions
      ADD COLUMN IF NOT EXISTS recap_days TEXT NOT NULL DEFAULT 'mon,tue,wed,thu,fri';

    ALTER TABLE alert_subscriptions
      ADD COLUMN IF NOT EXISTS last_recap_sent_at TIMESTAMPTZ;
    """

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
                cur.execute(alter)
        return {"ok": True, "skipped": False}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def upsert_subscription(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Router passes a dict with keys:
      email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes
    Optional recap keys:
      recap_enabled, recap_time_local, recap_timezone, recap_days
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

    # Recap defaults (only used if provided)
    recap_enabled = data.get("recap_enabled", None)
    recap_time_local = data.get("recap_time_local", None)
    recap_timezone = data.get("recap_timezone", None)
    recap_days = data.get("recap_days", None)

    if not email:
        return {"ok": False, "error": "email required"}
    if not tickers:
        return {"ok": False, "error": "tickers required"}
    if min_confidence not in ("LOW", "MEDIUM", "HIGH"):
        min_confidence = "MEDIUM"
    if source_pref not in ("auto", "cache", "live"):
        source_pref = "auto"

    # If recap fields are omitted, keep existing values on conflict update
    q = """
    INSERT INTO alert_subscriptions
      (email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes,
       recap_enabled, recap_time_local, recap_timezone, recap_days,
       updated_at)
    VALUES
      (%s, %s, %s, %s, %s, %s, %s, %s,
       COALESCE(%s, FALSE),
       COALESCE(%s, '21:00'),
       COALESCE(%s, 'America/New_York'),
       COALESCE(%s, 'mon,tue,wed,thu,fri'),
       NOW())
    ON CONFLICT (email)
    DO UPDATE SET
      enabled = EXCLUDED.enabled,
      tickers = EXCLUDED.tickers,
      min_prob_up = EXCLUDED.min_prob_up,
      min_confidence = EXCLUDED.min_confidence,
      horizon_days = EXCLUDED.horizon_days,
      source_pref = EXCLUDED.source_pref,
      cooldown_minutes = EXCLUDED.cooldown_minutes,
      recap_enabled = COALESCE(EXCLUDED.recap_enabled, alert_subscriptions.recap_enabled),
      recap_time_local = COALESCE(EXCLUDED.recap_time_local, alert_subscriptions.recap_time_local),
      recap_timezone = COALESCE(EXCLUDED.recap_timezone, alert_subscriptions.recap_timezone),
      recap_days = COALESCE(EXCLUDED.recap_days, alert_subscriptions.recap_days),
      updated_at = NOW()
    RETURNING
      id, email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes,
      recap_enabled, recap_time_local, recap_timezone, recap_days,
      last_sent_at, last_recap_sent_at, created_at, updated_at;
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
                        None if recap_enabled is None else bool(recap_enabled),
                        recap_time_local,
                        recap_timezone,
                        recap_days,
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
    SELECT
      id, email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes,
      recap_enabled, recap_time_local, recap_timezone, recap_days,
      last_sent_at, last_recap_sent_at, created_at, updated_at
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
    SELECT
      id, email, enabled, tickers, min_prob_up, min_confidence, horizon_days, source_pref, cooldown_minutes,
      recap_enabled, recap_time_local, recap_timezone, recap_days,
      last_sent_at, last_recap_sent_at, created_at, updated_at
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


def list_recap_enabled_subscriptions(limit: int = 2000) -> List[Dict[str, Any]]:
    """
    Recap runner uses this to find subscriptions that want daily recaps.
    """
    url = _db_url()
    if not url:
        return []

    limit = max(1, min(5000, int(limit)))

    q = """
    SELECT
      id, email, enabled, tickers,
      recap_enabled, recap_time_local, recap_timezone, recap_days,
      last_recap_sent_at,
      updated_at
    FROM alert_subscriptions
    WHERE enabled = TRUE AND recap_enabled = TRUE
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
    Remains "last overall alert email send" for visibility.
    """
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    email = (email or "").strip().lower()
    if not email:
        return {"ok": False, "error": "email required"}

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


def set_last_recap_sent_at(email: str, when_iso_utc: str) -> Dict[str, Any]:
    """
    Recap runner marks a recap as sent so we only send once per day.
    """
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    email = (email or "").strip().lower()
    if not email:
        return {"ok": False, "error": "email required"}

    try:
        when_dt = datetime.fromisoformat(when_iso_utc.replace("Z", "+00:00"))
    except Exception:
        when_dt = _utcnow()

    q = """
    UPDATE alert_subscriptions
    SET last_recap_sent_at = %s, updated_at = NOW()
    WHERE email = %s
    RETURNING id, email, last_recap_sent_at, updated_at;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (when_dt, email))
                row = cur.fetchone()
        return {"ok": True, "subscription": dict(row) if row else None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def update_recap_settings(
    email: str,
    recap_enabled: bool,
    recap_time_local: str,
    recap_timezone: str,
    recap_days: str,
) -> Dict[str, Any]:
    """
    Set recap preferences for a user.
    """
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    em = (email or "").strip().lower()
    if not em:
        return {"ok": False, "error": "email required"}

    q = """
    UPDATE alert_subscriptions
    SET
      recap_enabled = %s,
      recap_time_local = %s,
      recap_timezone = %s,
      recap_days = %s,
      updated_at = NOW()
    WHERE email = %s
    RETURNING
      id, email, recap_enabled, recap_time_local, recap_timezone, recap_days, last_recap_sent_at, updated_at;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (bool(recap_enabled), recap_time_local, recap_timezone, recap_days, em))
                row = cur.fetchone()
        return {"ok": True, "subscription": dict(row) if row else None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def insert_alert_events(email: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Store event_type='ALERT_TRIGGERED' with payload=hit.
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


def insert_email_sent_events(email: str, hits_sent: List[Dict[str, Any]], meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Insert event_type='EMAIL_SENT' per ticker actually included in an alert email.
    """
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    email = (email or "").strip().lower()
    if not email:
        return {"ok": False, "error": "email required"}

    meta = meta or {}

    rows = []
    for h in hits_sent or []:
        ticker = (h.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        payload = dict(h)
        payload["_meta"] = meta
        rows.append((email, ticker, "EMAIL_SENT", json.dumps(payload)))

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


def insert_recap_sent_event(email: str, tickers: List[str], payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a single recap event (ticker='ALL') for audit/history.
    """
    url = _db_url()
    if not url:
        return {"ok": False, "error": "DATABASE_URL not set"}

    em = (email or "").strip().lower()
    if not em:
        return {"ok": False, "error": "email required"}

    q = """
    INSERT INTO alert_events (email, ticker, event_type, payload)
    VALUES (%s, %s, %s, %s::jsonb);
    """

    safe_payload = dict(payload)
    safe_payload["tickers"] = [t.upper().strip() for t in (tickers or []) if (t or "").strip()]

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(q, (em, "ALL", "RECAP_SENT", json.dumps(safe_payload)))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_last_email_sent_by_ticker(email: str, tickers: List[str]) -> Dict[str, datetime]:
    """
    Returns { "SPY": <last EMAIL_SENT created_at>, ... } for this email.
    """
    url = _db_url()
    if not url:
        return {}

    email = (email or "").strip().lower()
    if not email:
        return {}

    tks = []
    seen = set()
    for t in tickers or []:
        tk = (t or "").upper().strip()
        if not tk or tk in seen:
            continue
        seen.add(tk)
        tks.append(tk)

    if not tks:
        return {}

    q = """
    SELECT ticker, MAX(created_at) AS last_sent_at
    FROM alert_events
    WHERE email = %s
      AND event_type = 'EMAIL_SENT'
      AND ticker = ANY(%s)
    GROUP BY ticker;
    """

    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(q, (email, tks))
                rows = cur.fetchall() or []
        out: Dict[str, datetime] = {}
        for r in rows:
            tk = (r.get("ticker") or "").upper().strip()
            dt = r.get("last_sent_at")
            if tk and isinstance(dt, datetime):
                out[tk] = dt
        return out
    except Exception:
        return {}


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
