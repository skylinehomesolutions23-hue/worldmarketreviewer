import pandas as pd
from pathlib import Path

REPORT_PATH = Path("results/integrated_risk_report.csv")
OUT_PATH = Path("results/capital_allocation_decision.csv")


def main():
    df = pd.read_csv(REPORT_PATH)

    allocation = 1.0
    reasons = []

    # Rolling risk
    rolling = df[df["section"] == "rolling_risk_latest"].iloc[0]

    beta = rolling.get("beta_6m", 0)
    vol = rolling.get("vol_6m", 0)
    max_dd = rolling.get("max_dd_12m", 0)

    if beta > 0.5:
        allocation *= 0.7
        reasons.append("High beta")

    if vol > df["vol_6m"].median():
        allocation *= 0.8
        reasons.append("Elevated volatility")

    if max_dd < -0.25:
        allocation = 0.0
        reasons.append("Drawdown kill-switch")

    # Tail risk
    tail = df[df["section"] == "tail_dependency"]
    if not tail.empty:
        tail_corr = tail["tail_corr"].iloc[0]
        if tail_corr < -0.3:
            allocation *= 1.1
            reasons.append("Negative tail correlation benefit")

    allocation = min(max(allocation, 0.0), 1.0)

    out = pd.DataFrame([{
        "final_allocation": allocation,
        "reasons": "; ".join(reasons)
    }])

    out.to_csv(OUT_PATH, index=False)

    print("Capital allocation decision complete.")
    print(out)


if __name__ == "__main__":
    main()
