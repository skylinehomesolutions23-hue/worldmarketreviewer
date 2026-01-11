import pandas as pd
import numpy as np

EQUITY_FILE = "results/walkforward_equity.csv"


def max_drawdown(series):
    peak = series.cummax()
    drawdown = (series / peak) - 1
    return drawdown.min()


def analyze():
    df = pd.read_csv(EQUITY_FILE)
    df["month"] = pd.to_datetime(df["month"])
    df = df.sort_values("month")

    equity = df["equity"]

    # --- Monthly returns
    returns = equity.pct_change().dropna()

    months = len(returns)
    years = months / 12

    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    vol = returns.std() * np.sqrt(12)
    sharpe = (returns.mean() * 12) / vol if vol != 0 else np.nan
    mdd = max_drawdown(equity)

    print("\n📊 WALK-FORWARD PERFORMANCE")
    print("=" * 35)
    print(f"Start Equity : {equity.iloc[0]:.2f}")
    print(f"End Equity   : {equity.iloc[-1]:.2f}")
    print(f"CAGR         : {cagr:.2%}")
    print(f"Volatility   : {vol:.2%}")
    print(f"Sharpe       : {sharpe:.2f}")
    print(f"Max Drawdown : {mdd:.2%}")
    print(f"Months       : {months}")
    print("=" * 35)

    # --- Save monthly returns
    out = pd.DataFrame({
        "month": df["month"].iloc[1:],
        "return": returns.values
    })

    out.to_csv("results/monthly_returns.csv", index=False)
    print("💾 Monthly returns saved → results/monthly_returns.csv\n")


if __name__ == "__main__":
    analyze()
