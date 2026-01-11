# logger.py

import datetime

def log(message: str):
    ts = datetime.datetime.utcnow().isoformat()
    print(f"[{ts}] {message}")
