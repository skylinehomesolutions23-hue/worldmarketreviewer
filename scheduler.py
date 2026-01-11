# scheduler.py

import threading
import time

from build_mobile_summary import main
from logger import log

INTERVAL_SECONDS = 60 * 30  # every 30 minutes

_scheduler_started = False


def _loop():
    log("Scheduler started")
    while True:
        try:
            log("Scheduler running build_mobile_summary()")
            main()
        except Exception as e:
            log(f"Scheduler error: {e}")
        time.sleep(INTERVAL_SECONDS)


def start():
    global _scheduler_started

    if _scheduler_started:
        log("Scheduler already running, skipping second start")
        return

    _scheduler_started = True
    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
