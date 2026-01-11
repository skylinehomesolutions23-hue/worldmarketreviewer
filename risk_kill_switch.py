import pandas as pd
from pathlib import Path

ROLLING_PATH = Path("results/diagnostics/rolling_risk_diagnostics.csv")
OUT_PATH = Path("results/kill_switch_status.csv")


def main():
    df = pd.read_csv(ROLLING_PATH, index_col=0, parse_dates=True)
    latest = df.iloc[-1]

    kill = False
    triggers = []

    if latest["max_dd_12m"] < -0.30:
        kill = True
        triggers.append("12m drawdown breach")

    if abs(latest["beta_3m"]) > 0.8:
        kill = True
        triggers.append("Short-term beta spike")

    out = pd.DataFrame([{
        "kill_switch": kill,
        "triggers": "; ".join(triggers)
    }])

    out.to_csv(OUT_PATH, index=False)

    print("Kill-switch evaluation complete.")
    print(out)


if __name__ == "__main__":
    main()
