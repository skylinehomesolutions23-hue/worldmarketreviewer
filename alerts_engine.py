# alerts_engine.py
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from alerts_db import (
    get_subscription,
    list_enabled_subscriptions,
    insert_alert_events,
    set_last_sent_at,
)

from db import get_latest_run_id, get_predictions_for_run


# -----------------------------
# config helpers
# -----------------------------
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def smtp_configured() -> bool:
    """
    Returns True if SMTP env vars are present.
    If False, the alerts system will still "simulate" alerts (log events),
    but it won't email anything.
    """
    host = (os.getenv("SMTP_HOST") or "").strip()
    user = (os.getenv("SMTP_USER") or "").strip()
    pwd = (os.getenv("SMTP_PASS") or "").strip()
    to_email = (os.getenv("ALERT_TO_EMAIL") or "").strip()
    return bool(host and user and pwd and to_email)


def _smtp_settings() -> Dict[str, Any]:
    return {
        "host": (os.getenv("SMTP_HOST") or "").strip(),
        "port": int(os.getenv("SMTP_PORT") or "587"),
        "user": (os.getenv("SMTP_USER") or "").strip(),
        "password": (os.getenv("SMTP_PASS") or "").strip(),
        "from_email": (os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_USER") or "").strip(),
        "to_email": (os.getenv("ALERT_TO_EMAIL") or "").strip(),
        "use_tls": (os.getenv("SMTP_USE_TLS") or "1").strip() not in ("0", "false", "False"),
    }


# -----------------------------
# email sending
# -----------------------------
def send_email_alert(subject: str, body: str) -> Dict[str, Any]:
    """
    Sends a basic plain-text email. Returns {ok: bool, ...}.
    Safe-by-default: if not configured, returns ok=False with a note.
    """
    if not smtp_configured():
        return {"ok": False, "note": "SMTP not configured. Set SMTP_* and ALERT_TO_EMAIL env vars."}

    cfg = _smtp_settings()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_email"]
    msg["To"] = cfg["to_email"]
    msg.set_content(body)

    try:
        if cfg["use_tls"]:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
                server.starttls()
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)

        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# -----------------------------
# predictions fetch
# -----------------------------
def fetch_predictions(run_id: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Pulls latest stored predictions from the DB.
    """
    if run_id is None:
        run_id = get_latest_run_id()
    if not run_id:
        return []

    preds = get_predictions_for_run(run_id, limit=max(1, int(limit)))
    # Ensure list[dict]
    out: List[Dict[str, Any]] = []
    for p in preds or []:
        if isinstance(p, dict):
            out.append(p)
    return out


# -----------------------------
# alert logic
# -----------------------------
def _confidence_rank(label: str) -> int:
    lab = (label or "").upper().strip()
    if lab == "HIGH":
        return 3
    if lab == "MEDIUM":
        return 2
    if lab == "LOW":
        return 1
    return 0


def cooldown_ok(user_id: str, ticker: str, cooldown_minutes: int = 60) -> bool:
    """
    Prevent spamming: only send once per cooldown window per ticker.
    Uses alerts_db subscription last_sent_at.
    """
    try:
        sub = get_subscription(user_id=user_id, ticker=ticker)
        if not sub:
            return True

        last = sub.get("last_sent_at")
        if not last:
            return True

        # last might be stored as ISO string
        if isinstance(last, str):
            try:
                # accept "2026-01-22T03:00:00Z" or with offset
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            except Exception:
                return True
        elif isinstance(last, datetime):
            last_dt = last
        else:
            return True

        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)

        return _utc_now() >= (last_dt + timedelta(minutes=int(cooldown_minutes)))
    except Exception:
        return True


def build_alert_items(
    subscriptions: List[Dict[str, Any]],
    predictions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Match subscriptions -> predictions and return alert items to send/log.
    Expected subscription fields (flexible):
      - user_id (default "demo")
      - ticker
      - enabled
      - min_confidence (LOW/MEDIUM/HIGH) optional
      - min_prob_up optional (float)
      - cooldown_minutes optional (int)
    """
    # Build quick map for latest prediction by ticker
    pred_by_ticker: Dict[str, Dict[str, Any]] = {}
    for p in predictions or []:
        t = (p.get("ticker") or "").upper().strip()
        if t:
            pred_by_ticker[t] = p

    items: List[Dict[str, Any]] = []

    for sub in subscriptions or []:
        if not sub:
            continue

        enabled = sub.get("enabled", True)
        if enabled is False:
            continue

        user_id = (sub.get("user_id") or "demo").strip()
        ticker = (sub.get("ticker") or "").upper().strip()
        if not ticker:
            continue

        p = pred_by_ticker.get(ticker)
        if not p:
            continue

        # Filters
        min_conf = (sub.get("min_confidence") or "").upper().strip()
        if min_conf:
            lab = (p.get("confidence") or "").upper().strip()
            if _confidence_rank(lab) < _confidence_rank(min_conf):
                continue

        min_prob_up = sub.get("min_prob_up")
        try:
            min_prob_up = float(min_prob_up) if min_prob_up is not None else None
        except Exception:
            min_prob_up = None

        if min_prob_up is not None:
            try:
                pu = float(p.get("prob_up"))
            except Exception:
                pu = None
            if pu is None or pu < min_prob_up:
                continue

        cooldown_minutes = sub.get("cooldown_minutes", 60)
        try:
            cooldown_minutes = int(cooldown_minutes)
        except Exception:
            cooldown_minutes = 60

        if not cooldown_ok(user_id, ticker, cooldown_minutes=cooldown_minutes):
            continue

        items.append(
            {
                "user_id": user_id,
                "ticker": ticker,
                "prob_up": p.get("prob_up"),
                "direction": p.get("direction"),
                "confidence": p.get("confidence"),
                "as_of_date": p.get("as_of_date"),
                "run_id": p.get("run_id") or p.get("runId") or None,
                "cooldown_minutes": cooldown_minutes,
            }
        )

    return items


def run_alert_check(user_id: str = "demo", limit_subs: int = 200) -> Dict[str, Any]:
    """
    End-to-end:
      - load enabled subscriptions
      - load latest predictions
      - build alert items
      - log events
      - send emails if configured
      - update last_sent_at
    """
    subs = list_enabled_subscriptions(user_id=user_id, limit=max(1, int(limit_subs)))
    preds = fetch_predictions()

    items = build_alert_items(subs, preds)
    if not items:
        return {"ok": True, "sent": 0, "logged": 0, "note": "No alerts to send."}

    # Log events (even if SMTP isn't configured)
    now_iso = _utc_now().isoformat()
    events = []
    for it in items:
        events.append(
            {
                "user_id": it["user_id"],
                "ticker": it["ticker"],
                "event_type": "ALERT_TRIGGERED",
                "payload": {
                    "prob_up": it.get("prob_up"),
                    "direction": it.get("direction"),
                    "confidence": it.get("confidence"),
                    "as_of_date": it.get("as_of_date"),
                },
                "created_at": now_iso,
            }
        )
    insert_alert_events(events)

    sent = 0
    if smtp_configured():
        # Send one email per item (simple + reliable)
        for it in items:
            subject = f"[WorldMarketReviewer] Alert: {it['ticker']} {it.get('direction')} ({it.get('confidence')})"
            body = (
                f"Ticker: {it['ticker']}\n"
                f"Direction: {it.get('direction')}\n"
                f"Prob Up: {it.get('prob_up')}\n"
                f"Confidence: {it.get('confidence')}\n"
                f"As Of: {it.get('as_of_date')}\n"
                f"Time (UTC): {now_iso}\n"
            )
            r = send_email_alert(subject=subject, body=body)
            if r.get("ok"):
                sent += 1

    # Update last_sent_at for cooldown tracking
    for it in items:
        set_last_sent_at(user_id=it["user_id"], ticker=it["ticker"])

    return {
        "ok": True,
        "matched": len(items),
        "logged": len(items),
        "sent": sent,
        "smtp_configured": smtp_configured(),
    }
