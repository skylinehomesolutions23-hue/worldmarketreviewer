import pandas as pd
import json
from pathlib import Path

RESULTS_DIR = Path("results")
INPUT_FILE = RESULTS_DIR / "mobile_summary.csv"
OUTPUT_FILE = RESULTS_DIR / "insight_summary.json"
PREF_FILE = Path("user_preferences.json")


def load_user_mode():
    if PREF_FILE.exists():
        with open(PREF_FILE, "r") as f:
            return json.load(f).get("explanation_mode", "GREEN")
    return "GREEN"


def explain_status(status: str, mode: str) -> str:
    explanations = {
        "GREEN": {
            "RISK_ON": "Conditions look favorable and the system sees healthy opportunity.",
            "RISK_OFF": "Risk is elevated, but the system is protecting capital.",
            "CAUTION": "Signals are mixed but manageable."
        },
        "YELLOW": {
            "RISK_ON": "Market conditions are stable, though risks still exist.",
            "RISK_OFF": "Market stress is present and caution is warranted.",
            "CAUTION": "Signals are conflicting and require attention."
        },
        "RED": {
            "RISK_ON": "Current exposure is allowed, but risk can change quickly.",
            "RISK_OFF": "High risk detected. Capital preservation is critical.",
            "CAUTION": "Uncertainty is elevated and defensive posture is advised."
        }
    }
    return explanations.get(mode, explanations["GREEN"]).get(
        status, "Market status is under evaluation."
    )


def beginner_notes(kill: bool, mode: str):
    if kill:
        return [
            "The system has detected elevated danger.",
            "Exposure has been restricted to protect capital."
        ]

    notes = {
        "GREEN": [
            "The system is operating normally.",
            "No major risks are currently detected."
        ],
        "YELLOW": [
            "The system is functioning but watching risk closely.",
            "Some caution is advised."
        ],
        "RED": [
            "The system is active, but risk awareness is critical.",
            "Stay alert to changing conditions."
        ]
    }
    return notes.get(mode, notes["GREEN"])


def pro_notes(sharpe: float, mode: str):
    if sharpe > 1:
        return [
            "Risk-adjusted performance remains favorable.",
            "Return profile is within expected tolerance."
        ]
    return [
        "Risk-adjusted returns are weakening.",
        "Performance efficiency should be monitored."
    ]


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE, parse_dates=["date"])
    latest = df.iloc[-1]

    mode = load_user_mode()

    insight = {
        "date": str(latest["date"]),
        "status": latest["status"],
        "explanation_mode": mode,
        "status_explainer": explain_status(latest["status"], mode),
        "kill_switch": bool(latest["kill_signal"]),
        "confidence_level": (
            "LOW" if latest["kill_signal"]
            else "HIGH" if latest.get("sharpe", 0) > 1
            else "MEDIUM"
        ),
        "beginner_notes": beginner_notes(latest["kill_signal"], mode),
        "pro_metrics": {
            "sharpe": round(latest.get("sharpe", 0), 3),
            "max_drawdown": round(latest.get("max_drawdown", 0), 3),
            "win_rate": round(latest.get("win_rate", 0), 3)
        },
        "pro_notes": pro_notes(latest.get("sharpe", 0), mode)
    }

    OUTPUT_FILE.write_text(json.dumps(insight, indent=2))
    print(f"✅ Insight summary created ({mode} mode):", OUTPUT_FILE)


if __name__ == "__main__":
    main()
