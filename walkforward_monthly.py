import pandas as pd
import numpy as np
from backtest_monthly import TOP_N

DATA = pd.read_csv("results/equity_monthly.csv")
DATA["date"] = pd.to_datetime(DATA["date"])

SPLIT = int(len(DATA) * 0.7)

train = DATA.iloc[:SPLIT]
test = DATA.iloc[SPLIT:]

def stats(df):
    rets = df["return"]
    cagr = (df["equity"].iloc[-1] / df["equity"].iloc[0]) ** (12/len(df)) - 1
    sharpe = np.sqrt(12) * rets.mean() / rets.std()
    dd = (df["equity"] / df["equity"].cummax() - 1).min()
    return cagr, sharpe, dd

train_stats = stats(train)
test_stats = stats(test)

print("\n=== WALK FORWARD RESULTS ===")
print(f"IN-SAMPLE  | CAGR {train_stats[0]:.2%} | Sharpe {train_stats[1]:.2f} | DD {train_stats[2]:.2%}")
print(f"OUT-SAMPLE | CAGR {test_stats[0]:.2%} | Sharpe {test_stats[1]:.2f} | DD {test_stats[2]:.2%}")
