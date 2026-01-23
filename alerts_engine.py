# alerts_engine.py
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

# -------------------------------------------------
# Email / SMTP (stub-safe)
# -------------------------------------------------

def smtp_configured() -> bool:
    """
    Returns True if SMTP env vars are present.
    Safe to call even if email isn't set up yet.
    """
    return bool(
        os.getenv("SMTP_HOST")
        and os.getenv("SMTP_USER")
        and os.getenv("SMTP_PASSWORD")
    )


def send_email_alert(
    to_email: str,
    subject: str,
    body: str,
) -> Dict[str, Any]:
    """
    Placeholder email sender.
    Does NOT crash if SMTP isn't configured.
    """
    if not smtp_configured():
        return {
            "ok": False,
            "skipped": True,
            "reason": "SMTP not configured",
        }

    # You can implement real SMTP later
    # For now, keep API stable
    return {
        "ok": True,
        "sent": False,
        "note": "SMTP configured but send not implemented yet",
    }


# -------------------------------------------------
# Alert logic
# -------------------------------------------------

def cooldown_ok(
    last_sent_at: Optional[datetime],
    cooldown_minutes: int = 60,
) -> bool:
    """
    Prevents alert spam.
    Returns True if enough time has passed.
    """
    if last_sent_at is None:
        return True

    if last_sent_at.tzinfo is None:
        last_sent_at = last_sent_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    return now - last_sent_at >= timedelta(minutes=cooldown_minutes)


def run_alert_check(
    subscription: Dict[str, Any],
    prediction: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Decides whether an alert should fire.
    This is intentionally simple and deterministic.
    """

    if not subscription.get("enabled", False):
        return {"fire": False, "reason": "disabled"}

    prob_up = prediction.get("prob_up")
    direction = prediction.get("direction")
    threshold = subscription.get("threshold_prob", 0.65)

    if prob_up is None:
        return {"fire": False, "reason": "missing_prob"}

    if direction != subscription.get("direction", "UP"):
        return {"fire": False, "reason": "direction_mismatch"}

    if float(prob_up) < float(threshold):
        return {"fire": False, "reason": "below_threshold"}

    return {
        "fire": True,
        "reason": "threshold_met",
        "prob_up": prob_up,
        "threshold": threshold,
    }
