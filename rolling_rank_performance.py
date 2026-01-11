# rolling_rank_performance.py

import pandas as pd
import os

INPUT_FILE = "data/forward_returns.csv"
OUTPUT_FILE = "results/rolling_rank_performance.csv"

WINDOW_MONTHS = 60  # 5 years


def main():
    df = pd.read_csv(INPUT_FILE, parse_dates=["date"])

    df = df.sort_values("date")

    rows = []

    for rank in sorted(df["rank"].unique()):
        sub = df[df["rank"] == rank].copy()

        sub["rolling_mean"] = (
            sub.set_index("date")["forward_return"]
            .rolling(WINDOW_MONTHS)
            .mean()
            .values
        )

        sub = sub.dropna(subset=["rolling_mean"])

        for _, r in sub.iterrows():
            rows.append({
                "date": r["date"],
                "rank": rank,
                "rolling_mean_return": r["rolling_mean"]
            })

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_FILE, index=False)

    print("📈 Rolling rank performance saved → results/rolling_rank_performance.csv")


if __name__ == "__main__":
    main()
