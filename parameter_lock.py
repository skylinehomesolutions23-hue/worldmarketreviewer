# parameter_lock.py

import json
import hashlib
import pandas as pd
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PROJECT_ROOT / "parameter_manifest.json"
LOCK_PATH = PROJECT_ROOT / "results" / "parameter_lock.csv"


def hash_manifest() -> str:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"❌ parameter_manifest.json not found at:\n{MANIFEST_PATH}"
        )

    with open(MANIFEST_PATH, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_previous_hash():
    if not LOCK_PATH.exists():
        return None
    df = pd.read_csv(LOCK_PATH)
    return df["hash"].iloc[-1]


def lock_parameters():
    current_hash = hash_manifest()
    previous_hash = load_previous_hash()

    status = "UNCHANGED"
    if previous_hash and previous_hash != current_hash:
        status = "CHANGED"

    row = {
        "timestamp": datetime.utcnow(),
        "hash": current_hash,
        "status": status
    }

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(LOCK_PATH)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    except FileNotFoundError:
        df = pd.DataFrame([row])

    df.to_csv(LOCK_PATH, index=False)

    if status == "CHANGED":
        raise RuntimeError(
            "❌ PARAMETER DRIFT DETECTED\n"
            "Review parameter_manifest.json before proceeding."
        )

    return row


if __name__ == "__main__":
    try:
        result = lock_parameters()
        print("🔒 Parameter lock status:", result["status"])
    except Exception as e:
        print(str(e))
        sys.exit(1)
