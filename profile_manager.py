import json
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"


def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError("config.json not found")

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def set_active_profile(profile_name: str):
    config = load_config()

    if profile_name not in config["profiles"]:
        return {"status": "error", "message": f"Profile '{profile_name}' not found"}

    config["active_profile"] = profile_name
    save_config(config)

    return {"status": "ok", "active_profile": profile_name}
