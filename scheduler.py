# scheduler.py

import time
from build_mobile_summary import main
from tracker import record
from logger import log
from settings import RUN_EVERY_SECONDS


def run_forever():
    log("Scheduler started")

    while True:
        try:
            summary = main()
            record(summary)
        except Exception as e:
            log(f"Scheduler error: {e}")

        time.sleep(RUN_EVERY_SECONDS)


if __name__ == "__main__":
    run_forever()
