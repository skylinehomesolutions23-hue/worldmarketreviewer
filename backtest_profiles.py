import pandas as pd
from pathlib import Path

DATA = Path("data/monthly_returns.csv")

def backtest():
    df = pd.read_csv(DATA)
    df["return"] = df.iloc[:, 1]

    profiles = {
        "conservative": 0.5,
        "balanced": 0.75,
        "aggressive": 1.0
    }

    results = {}
    for name, exp in profiles.items():
        equity = (1 + df["return"] * exp).cumprod()
        results[name] = round(equity.iloc[-1], 4)

    return results
