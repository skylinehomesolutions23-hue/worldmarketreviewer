import json
from pathlib import Path

PREFS_FILE = Path("config/user_preferences.json")


def load_preferences():
    if not PREFS_FILE.exists():
        raise FileNotFoundError("Missing config/user_preferences.json")

    with open(PREFS_FILE, "r") as f:
        return json.load(f)
