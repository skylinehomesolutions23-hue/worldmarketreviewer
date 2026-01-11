# save_signals.py
import os
import pandas as pd


def save_month_signals(df: pd.DataFrame, month_tag: str, top_n: int = 10):
    if not {"ticker", "score"}.issubset(df.columns):
        raise ValueError("DataFrame must contain ticker and score")

    ranked = (
        df.dropna()
        .sort_values("score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )

    os.makedirs("outputs", exist_ok=True)
    path = f"outputs/signals_{month_tag}.csv"
    ranked.to_csv(path, index=False)

    print(f"💾 Signals saved → {path}")
