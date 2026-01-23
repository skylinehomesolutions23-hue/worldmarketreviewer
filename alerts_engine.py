import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def smtp_configured() -> bool:
    """
    Subscriber-email mode:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM_EMAIL must be set.
    """
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = (os.getenv("SMTP_PORT") or "").strip()
    user = (os.getenv("SMTP_USER") or "").strip()
    pwd = (os.getenv("SMTP_PASS") or "").strip()
    from_email = (os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_USER") or "").strip()
    return bool(host and port and user and pwd and from_email)


def _smtp_settings() -> Dict[str, Any]:
    return {
        "host": (os.getenv("SMTP_HOST") or "").strip(),
        "port": int((os.getenv("SMTP_PORT") or "587").strip()),
        "user": (os.getenv("SMTP_USER") or "").strip(),
        "password": (os.getenv("SMTP_PASS") or "").strip(),
        "from_email": (os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_USER") or "").strip(),
        "use_tls": (os.getenv("SMTP_USE_TLS") or "1").strip() not in ("0", "false", "False"),
    }


def send_email_alert(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Sends a basic plain-text email to the subscriber.
    """
    if not smtp_configured():
        return {"ok": False, "note": "SMTP not configured. Set SMTP_* env vars."}

    cfg = _smtp_settings()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_email"]
    msg["To"] = (to_email or "").strip().lower()
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


def _confidence_rank(label: str) -> int:
    lab = (label or "").upper().strip()
    if lab == "HIGH":
        return 3
    if lab == "MEDIUM":
        return 2
    if lab == "LOW":
        return 1
    return 0


def cooldown_ok(last_sent_at: Optional[Any], cooldown_minutes: int) -> bool:
    """
    Router passes last_sent_at from DB (could be None, datetime, or ISO string).
    """
    if not last_sent_at:
        return True

    try:
        if isinstance(last_sent_at, str):
            last_dt = datetime.fromisoformat(last_sent_at.replace("Z", "+00:00"))
        elif isinstance(last_sent_at, datetime):
            last_dt = last_sent_at
        else:
            return True

        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)

        return _utc_now() >= (last_dt + timedelta(minutes=int(cooldown_minutes)))
    except Exception:
        return True


def run_alert_check(
    email: str,
    tickers: List[str],
    min_prob_up: float,
    min_confidence: str,
    horizon_days: int,
    source_pref: str,
    max_parallel: int = 4,
    retrain: bool = False,
) -> Dict[str, Any]:
    """
    Uses your existing /api/summary endpoint internally so alerts logic stays consistent.
    This avoids re-implementing prediction logic here.

    It calls:
      GET/POST local summary handler is not directly accessible here,
      so we import and call the same internal functions you already have in api.py:
        - create_run / insert_predictions etc. would be heavy
      Instead: for now, we call the live API via httpx against BASE_URL.

    BASE_URL:
      - if running on Render: use PUBLIC_BASE_URL or fallback to https://worldmarketreviewer.onrender.com
      - if running locally: set PUBLIC_BASE_URL=http://127.0.0.1:8000
    """
    import httpx  # already in requirements

    base = (os.getenv("PUBLIC_BASE_URL") or "https://worldmarketreviewer.onrender.com").rstrip("/")
    url = f"{base}/api/summary"

    payload = {
        "tickers": tickers,
        "retrain": bool(retrain),
        "horizon_days": int(horizon_days),
        "base_weekly_move": 0.02,
        "max_parallel": int(max_parallel),
        "min_confidence": None,
        "min_prob_up": None,
        "source_pref": source_pref,
    }

    errors: Dict[str, Any] = {}
    hits: List[Dict[str, Any]] = []

    try:
        with httpx.Client(timeout=60) as client:
            r = client.post(url, json=payload)
            if r.status_code != 200:
                return {
                    "ok": False,
                    "hits": [],
                    "errors": {"summary_http": f"{r.status_code}: {r.text[:200]}"},
                }
            summary = r.json()
    except Exception as e:
        return {"ok": False, "hits": [], "errors": {"summary_call": str(e)}}

    rows = summary.get("rows") or summary.get("results") or summary.get("summary") or []
    if not isinstance(rows, list):
        rows = []

    want_conf = (min_confidence or "MEDIUM").upper().strip()
    want_prob = float(min_prob_up or 0.65)

    for row in rows:
        try:
            t = (row.get("ticker") or "").upper().strip()
            if not t:
                continue

            pu = row.get("prob_up")
            try:
                pu_f = float(pu)
            except Exception:
                pu_f = None

            conf = (row.get("confidence") or row.get("confidence_label") or "").upper().strip()
            as_of = row.get("as_of_date") or row.get("date") or row.get("as_of") or None
            src = row.get("source") or row.get("data_source") or None

            if pu_f is None:
                continue
            if pu_f < want_prob:
                continue
            if conf and _confidence_rank(conf) < _confidence_rank(want_conf):
                continue

            hits.append(
                {
                    "ticker": t,
                    "prob_up": pu_f,
                    "confidence": conf or "UNKNOWN",
                    "as_of_date": as_of,
                    "source": src,
                }
            )
        except Exception as e:
            errors[str(row.get("ticker") or "row_error")] = str(e)

    return {"ok": True, "hits": hits, "errors": errors}
