# exposure_decision_tree.py

import pandas as pd

from ops_guardrails import evaluate_guardrails
from discretionary_override import apply_discretionary_override

SYSTEMATIC_EXPOSURE_PATH = "results/final_exposure_curve.csv"
OUTPUT_PATH = "results/final_exposure_resolved.csv"


def load_systematic_exposure():
    df = pd.read_csv(SYSTEMATIC_EXPOSURE_PATH, parse_dates=["date"])
    return float(df["exposure"].iloc[-1])


def resolve_exposure():
    base_exposure = load_systematic_exposure()

    guardrail_exposure, guardrail_reason = evaluate_guardrails()
    post_guardrail = min(base_exposure, guardrail_exposure)

    final_exposure, override_reason = apply_discretionary_override(post_guardrail)

    row = {
        "date": pd.Timestamp.today().normalize(),
        "base_exposure": base_exposure,
        "guardrail_exposure": post_guardrail,
        "final_exposure": final_exposure,
        "guardrail_reason": guardrail_reason,
        "override_reason": override_reason,
    }

    pd.DataFrame([row]).to_csv(OUTPUT_PATH, index=False)
    return row


if __name__ == "__main__":
    result = resolve_exposure()
    print("Final exposure decision:")
    print(result)
