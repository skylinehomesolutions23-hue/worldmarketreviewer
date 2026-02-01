# alerts_engine.py
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ----------------------------
# Email provider configuration
# ----------------------------

def resend_configured() -> bool:
    key = (os.getenv("RESEND_API_KEY") or "").strip()
    from_email = (os.getenv("RESEND_FROM_EMAIL") or "").strip()
    return bool(key and from_email)


def smtp_configured() -> bool:
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


def _send_via_resend(to_email: str, subject: str, body_text: str) -> Dict[str, Any]:
    """
    Sends email using Resend HTTP API.
    Requires:
      RESEND_API_KEY
      RESEND_FROM_EMAIL
    Optional:
      RESEND_FROM_NAME
    """
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    from_email = (os.getenv("RESEND_FROM_EMAIL") or "").strip()
    from_name = (os.getenv("RESEND_FROM_NAME") or "WorldMarketReviewer").strip()

    if not (api_key and from_email):
        return {"ok": False, "provider": "resend", "note": "Resend not configured"}

    # Resend expects "From" like: "Name <email@domain>"
    from_header = f"{from_name} <{from_email}>"

    payload = {
        "from": from_header,
        "to": [(to_email or "").strip().lower()],
        "subject": subject,
        # Use text for reliability; you can add HTML later if you want
        "text": body_text,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=25) as client:
            r = client.post("https://api.resend.com/emails", headers=headers, json=payload)

        if r.status_code in (200, 201):
            # Resend returns JSON like {"id":"..."}
            try:
                data = r.json()
            except Exception:
                data = {}
            return {"ok": True, "provider": "resend", "status_code": r.status_code, "id": data.get("id")}

        # Return a small slice of the error text
        return {"ok": False, "provider": "resend", "status_code": r.status_code, "error": r.text[:500]}
    except Exception as e:
        return {"ok": False, "provider": "resend", "error": str(e)}


def _send_via_smtp(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    if not smtp_configured():
        return {"ok": False, "provider": "smtp", "note": "SMTP not configured. Set SMTP_* env vars."}

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

        return {"ok": True, "provider": "smtp"}
    except Exception as e:
        return {"ok": False, "provider": "smtp", "error": str(e)}


def send_email_alert(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Provider selection:
      1) Resend (preferred on Render)
      2) SMTP fallback (useful locally)
    """
    if resend_configured():
        out = _send_via_resend(to_email, subject, body)
        # If Resend is configured but fails, return its error (don't silently fallback)
        return out

    return _send_via_smtp(to_email, subject, body)


# ----------------------------
# Alert logic helpers
# ----------------------------

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
    Calls your own /api/summary endpoint and filters rows to produce alert hits.
    """
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

    try:
        with httpx.Client(timeout=90) as client:
            r = client.post(url, json=payload)
            if r.status_code != 200:
                return {"ok": False, "hits": [], "errors": {"summary_http": f"{r.status_code}: {r.text[:300]}"}}
            summary = r.json()
    except Exception as e:
        return {"ok": False, "hits": [], "errors": {"summary_call": str(e)}}

    rows = summary.get("predictions") or []
    if not isinstance(rows, list):
        rows = []

    want_conf = (min_confidence or "MEDIUM").upper().strip()
    want_prob = float(min_prob_up if min_prob_up is not None else 0.65)

    errors: Dict[str, Any] = {}
    hits: List[Dict[str, Any]] = []

    for row in rows:
        try:
            t = (row.get("ticker") or "").upper().strip()
            if not t:
                continue

            try:
                pu_f = float(row.get("prob_up"))
            except Exception:
                pu_f = None

            conf = (
                row.get("confidence")
                or row.get("confidence_label")
                or row.get("confidence_bucket")
                or ""
            )
            conf = (conf or "").upper().strip()

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
