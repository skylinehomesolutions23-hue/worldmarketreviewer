import pandas as pd
import numpy as np
import os

FILE = "results/factor_returns.csv"
OUT = "results/factor_equity_vol_targeted.csv"

TARGET_VOL = 0.10
MAX_LEVERAGE = 1.5


def main():
    df = pd.read_csv(FILE, parse_dates=["date"])
    df = df.sort_values("date")

    df["rolling_vol"] = (
        df["factor_return"]
        .rolling(12)
        .std()
        * np.sqrt(12)
    )

    df["vol_scalar"] = TARGET_VOL / df["rolling_vol"]
    df["vol_scalar"] = df["vol_scalar"].clip(0, MAX_LEVERAGE)
    df["vol_scalar"] = df["vol_scalar"].fillna(1.0)

    df["scaled_return"] = df["factor_return"] * df["vol_scalar"]

    equity = []
    eq = 1.0
    for r in df["scaled_return"]:
        eq *= (1 + r)
        equity.append(eq)

    df["equity"] = equity

    os.makedirs("results", exist_ok=True)
    df[["date", "equity"]].to_csv(OUT, index=False)

    print("📈 Vol-targeted factor equity saved →", OUT)
    print(df.tail())


if __name__ == "__main__":
    main()
