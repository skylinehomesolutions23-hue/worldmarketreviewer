# factor_equity_curve.py

import pandas as pd
import os

INPUT_FILE = "results/factor_returns.csv"
OUTPUT_FILE = "results/factor_equity.csv"


def main():
    df = pd.read_csv(INPUT_FILE, parse_dates=["date"])

    if df.empty:
        raise RuntimeError("Factor returns file is empty")

    df["equity"] = (1 + df["factor_return"]).cumprod()

    equity = df[["date", "equity"]]

    os.makedirs("results", exist_ok=True)
    equity.to_csv(OUTPUT_FILE, index=False)

    print(f"📈 Factor equity curve saved → {OUTPUT_FILE}")
    print(equity.head())


if __name__ == "__main__":
    main()
