# feature_engineering.py
from __future__ import annotations

import pandas as pd


def _ensure_price_col(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure we have a 'Price' column.
    Accepts common alternatives like Close/close/Adj Close, etc.
    """
    if df is None or df.empty:
        raise ValueError("build_features expects a non-empty DataFrame")

    out = df.copy()

    if "Price" in out.columns:
        return out

    # common alternatives
    for c in ["close", "Close", "adj_close", "Adj Close", "AdjClose", "adjclose", "price", "Price"]:
        if c in out.columns:
            out["Price"] = pd.to_numeric(out[c], errors="coerce")
            return out

    raise ValueError("build_features expects a DataFrame with a usable price column (Price/Close/etc).")


def build_features(df: pd.DataFrame, horizon_days: int = 5) -> pd.DataFrame:
    """
    Build simple technical features and a horizon-aware target.

    Input df:
      index: datetime (UTC OK)
      columns: includes a price column ('Price' preferred; Close variants accepted)

    Output df:
      columns include:
        - returns, ma5, ma10, volatility
        - target = 1 if Price[t+horizon_days] > Price[t] else 0
    """
    horizon_days = max(1, int(horizon_days))

    out = _ensure_price_col(df)

    out["returns"] = out["Price"].pct_change()
    out["ma5"] = out["Price"].rolling(5).mean()
    out["ma10"] = out["Price"].rolling(10).mean()
    out["volatility"] = out["returns"].rolling(10).std()

    # Horizon-aware target (trading bars, not calendar days)
    out["target"] = (out["Price"].shift(-horizon_days) > out["Price"]).astype(int)

    # Keep a clean training set
    out = out.dropna().copy()

    return out
