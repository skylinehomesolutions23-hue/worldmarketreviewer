# subperiod_equity.py

import pandas as pd
import os

INPUT_FILE = "results/factor_equity.csv"
OUTPUT_FILE = "results/subperiod_equity.csv"

PERIODS = {
    "2005-2012": ("2005-01-01", "2012-12-31"),
    "2013-2019": ("2013-01-01", "2019-12-31"),
    "2020-present": ("2020-01-01", "2100-01-01"),
}


def main():
    df = pd.read_csv(INPUT_FILE, parse_dates=["date"])

    rows = []

    for name, (start, end) in PERIODS.items():
        sub = df[(df["date"] >= start) & (df["date"] <= end)].copy()
        if len(sub) == 0:
            continue

        start_equity = sub.iloc[0]["equity"]
        end_equity = sub.iloc[-1]["equity"]

        rows.append({
            "period": name,
            "return": end_equity / start_equity - 1
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_FILE, index=False)

    print("📊 Subperiod equity saved → results/subperiod_equity.csv")


if __name__ == "__main__":
    main()
