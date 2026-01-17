# feature_engineering.py
import pandas as pd


def build_features(df: pd.DataFrame, horizon_days: int = 1) -> pd.DataFrame:
    """
    Build technical features and a horizon-aware target.

    Expected input:
      - DataFrame indexed by datetime (or contains a date index)
      - column: 'Price'

    Output:
      - adds feature columns (returns, ma5, ma10, volatility, etc.)
      - adds target column:
          target = 1 if Price[t + horizon_days] > Price[t] else 0

    Notes:
      - Your current data is MONTHLY, so horizon_days is actually "rows ahead".
      - If you later switch to DAILY data, horizon_days becomes actual trading days ahead.
    """
    df = df.copy()

    if "Price" not in df.columns:
      raise ValueError("build_features expected a 'Price' column")

    # sanitize horizon
    try:
      h = int(horizon_days)
    except Exception:
      h = 1
    h = max(1, h)

    # basic return features
    df["returns"] = df["Price"].pct_change()

    # moving averages
    df["ma5"] = df["Price"].rolling(5).mean()
    df["ma10"] = df["Price"].rolling(10).mean()

    # volatility
    df["volatility"] = df["returns"].rolling(10).std()

    # optional momentum-ish features (help reduce "randomness" a bit)
    df["mom3"] = df["Price"].pct_change(3)
    df["mom6"] = df["Price"].pct_change(6)

    # horizon-aware target:
    # compare future price to current
    df["future_price"] = df["Price"].shift(-h)
    df["target"] = (df["future_price"] > df["Price"]).astype(int)

    # clean up
    df = df.dropna()

    # don't leak future_price as a feature
    df = df.drop(columns=["future_price"], errors="ignore")

    return df
