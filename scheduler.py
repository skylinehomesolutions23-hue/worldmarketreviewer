import threading
import time
from build_mobile_summary import main
from logger import log

INTERVAL_SECONDS = 60 * 30  # every 30 minutes


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
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
