import pandas as pd
from pathlib import Path

DECAY_DIR = Path("results/decay")

MIN_SHARPE = 0.5
MIN_ROLLING_RETURN = 0.0


def main():
    risk = pd.read_csv(DECAY_DIR / "risk_metrics.csv")
    perf = pd.read_csv(DECAY_DIR / "portfolio_returns.csv")

    latest_rolling = perf["rolling_net"].iloc[-1]
    sharpe = risk["sharpe"].iloc[0]

    kill = False
    reasons = []

    if sharpe < MIN_SHARPE:
        kill = True
        reasons.append("LOW_SHARPE")

    if latest_rolling < MIN_ROLLING_RETURN:
        kill = True
        reasons.append("NEGATIVE_ROLLING_RETURN")

    result = pd.DataFrame([{
        "date": perf["date"].iloc[-1],
        "sharpe": sharpe,
        "rolling_net_return": latest_rolling,
        "kill_signal": kill,
        "reason": "|".join(reasons) if reasons else "EDGE_HEALTHY"
    }])

    out = DECAY_DIR / "signal_kill_decision_v2.csv"
    result.to_csv(out, index=False)

    print("✅ Auto-kill v2 decision complete")
    print(result)


if __name__ == "__main__":
    main()
