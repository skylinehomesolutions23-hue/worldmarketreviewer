# apply_regime_to_equity.py
import pandas as pd

EQUITY_FILE = "results/portfolio_monthly_equity.csv"
REGIME_FILE = "data/regime.csv"
OUT_FILE = "results/portfolio_equity_regime.csv"

def main():
    eq = pd.read_csv(EQUITY_FILE, parse_dates=["date"])
    reg = pd.read_csv(REGIME_FILE, parse_dates=["date"])

    df = eq.merge(reg, on="date", how="left")
    df["exposure"] = df["exposure"].fillna(1.0)

    df["ret"] = df["equity"].pct_change().fillna(0)
    df["adj_ret"] = df["ret"] * df["exposure"]
    df["equity"] = (1 + df["adj_ret"]).cumprod()

    df[["date", "equity"]].to_csv(OUT_FILE, index=False)

    print(f"📈 Regime-adjusted equity saved → {OUT_FILE}")
    print(df.head())

if __name__ == "__main__":
    main()
