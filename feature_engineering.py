# feature_engineering.py
from __future__ import annotations

import pandas as pd


def build_features(df: pd.DataFrame, horizon_days: int = 5) -> pd.DataFrame:
    """
    Build simple technical features and a horizon-aware target.

    Input df:
      index: datetime
      columns: ['Price']

    Output df:
      columns include:
        - returns, ma5, ma10, volatility
        - target = 1 if Price[t+horizon_days] > Price[t] else 0
    """
    horizon_days = max(1, int(horizon_days))

    out = df.copy()

    # Ensure we have the expected column
    if "Price" not in out.columns:
        raise ValueError("build_features expects a DataFrame with column 'Price'")

    out["returns"] = out["Price"].pct_change()
    out["ma5"] = out["Price"].rolling(5).mean()
    out["ma10"] = out["Price"].rolling(10).mean()
    out["volatility"] = out["returns"].rolling(10).std()

    # Horizon-aware target
    out["target"] = (out["Price"].shift(-horizon_days) > out["Price"]).astype(int)

    # Keep a clean training set
    out = out.dropna().copy()

    return out
