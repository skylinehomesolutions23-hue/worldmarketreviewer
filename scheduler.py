# scheduler.py

import threading
import time
from build_mobile_summary import main
from logger import log

INTERVAL_SECONDS = 60 * 30  # 30 minutes
_started = False


def loop():
    log("Scheduler started")
    while True:
        try:
            log("Scheduler running build_mobile_summary()")
            main()
        except Exception as e:
            log(f"Scheduler error: {e}")
        time.sleep(INTERVAL_SECONDS)


def start():
    global _started

    if _started:
        log("Scheduler already running, skipping duplicate start")
        return

    _started = True
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
