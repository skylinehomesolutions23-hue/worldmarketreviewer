import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
TOP_N = 10

def main():
    df = pd.read_csv(RESULTS_DIR / "all_monthly_signals.csv")
    df = df[df["rank"] <= TOP_N]

    months = sorted(df["month"].unique())

    rows = []

    for i in range(len(months) - 1):
        m1 = months[i]
        m2 = months[i + 1]

        set1 = set(df[df["month"] == m1]["ticker"])
        set2 = set(df[df["month"] == m2]["ticker"])

        stayed = len(set1 & set2)
        turnover = 1 - (stayed / TOP_N)

        rows.append({
            "from_month": m1,
            "to_month": m2,
            "stayed": stayed,
            "turnover_pct": turnover
        })

    out = pd.DataFrame(rows)
    out.to_csv(RESULTS_DIR / "signal_turnover.csv", index=False)
    print("🔁 Turnover stats saved → results/signal_turnover.csv")

if __name__ == "__main__":
    main()
