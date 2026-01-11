# discretionary_override.py

import pandas as pd
from datetime import datetime

# =========================
# MANUAL OVERRIDE SETTINGS
# =========================

OVERRIDE_ACTIVE = False            # MUST be explicitly set to True
OVERRIDE_MAX_EXPOSURE = 0.25       # Cap exposure if active (None = full freeze)
OVERRIDE_REASON = ""               # REQUIRED if active
OVERRIDE_EXPIRY = "2099-12-31"     # Auto-disable after this date (YYYY-MM-DD)

LOG_PATH = "results/discretionary_override_log.csv"


def override_is_valid():
    if not OVERRIDE_ACTIVE:
        return False

    if not OVERRIDE_REASON:
        raise ValueError("Override active but OVERRIDE_REASON is empty")

    expiry = pd.to_datetime(OVERRIDE_EXPIRY)
    return pd.Timestamp.today() <= expiry


def apply_discretionary_override(exposure: float):
    if not override_is_valid():
        return exposure, "NO_OVERRIDE"

    if OVERRIDE_MAX_EXPOSURE is None:
        return 0.0, f"OVERRIDE_FREEZE: {OVERRIDE_REASON}"

    return min(exposure, OVERRIDE_MAX_EXPOSURE), f"OVERRIDE_CAP: {OVERRIDE_REASON}"


def log_override():
    row = {
        "timestamp": datetime.utcnow(),
        "active": OVERRIDE_ACTIVE,
        "max_exposure": OVERRIDE_MAX_EXPOSURE,
        "reason": OVERRIDE_REASON,
        "expiry": OVERRIDE_EXPIRY,
    }

    try:
        df = pd.read_csv(LOG_PATH)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    except FileNotFoundError:
        df = pd.DataFrame([row])

    df.to_csv(LOG_PATH, index=False)


if __name__ == "__main__":
    log_override()
    print("Discretionary override evaluated and logged.")
