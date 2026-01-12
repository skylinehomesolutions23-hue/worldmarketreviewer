# health.py
from datetime import datetime
import os

def check():
    return {
        "status": "ok",
        "service": "worldmarketreviewer",
        "version": os.getenv("APP_VERSION", "0.1.0"),
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
