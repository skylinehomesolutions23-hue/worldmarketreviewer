from utils.preferences import load_preferences
from utils.explanations import explain_status
import pandas as pd

STATUS_MAP = {
    "RISK_ON": "GREEN",
    "CAUTION": "YELLOW",
    "RISK_OFF": "RED"
}


def main():
    prefs = load_preferences()

    summary = pd.read_csv("results/mobile_summary.csv")
    status = summary.loc[0, "status"]

    color = STATUS_MAP.get(status, "YELLOW")
    explanation = explain_status(color, prefs)

    summary["explanation"] = explanation
    summary["risk_color"] = color

    summary.to_csv(
        "results/explained_mobile_summary.csv",
        index=False
    )

    print("✅ Explained insight summary created")
