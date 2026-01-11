# turnover_and_costs.py

import pandas as pd

PORT = "results/monthly_portfolio.csv"
OUT = "results/turnover.csv"

COST_PER_TRADE = 0.001  # 10 bps per full turnover


def main():
    df = pd.read_csv(PORT, parse_dates=["month"])
    df = df.sort_values(["ticker", "month"])

    df["prev_weight"] = df.groupby("ticker")["weight"].shift(1)
    df["trade"] = (df["weight"] - df["prev_weight"]).abs()
    df["trade"] = df["trade"].fillna(df["weight"])

    monthly = df.groupby("month")["trade"].sum()
    costs = monthly * COST_PER_TRADE

    out = pd.DataFrame({
        "turnover": monthly,
        "cost": costs
    })

    out.to_csv(OUT)
    print("💸 Turnover & transaction costs saved →", OUT)
    print(out.head())


if __name__ == "__main__":
    main()
