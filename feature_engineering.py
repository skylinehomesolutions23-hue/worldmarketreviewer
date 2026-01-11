import pandas as pd
import numpy as np


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ---------------------------------
    # FIX: Flatten MultiIndex columns
    # ---------------------------------
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            col[0].lower() if isinstance(col, tuple) else col.lower()
            for col in df.columns
        ]
    else:
        df.columns = [col.lower() for col in df.columns]

    # ---------------------------------
    # Basic returns
    # ---------------------------------
    df["return_1"] = df["close"].pct_change()
    df["return_5"] = df["close"].pct_change(5)

    # ---------------------------------
    # Moving averages
    # ---------------------------------
    df["sma_20"] = df["close"].rolling(20).mean()
    df["sma_50"] = df["close"].rolling(50).mean()
    df["sma_200"] = df["close"].rolling(200).mean()

    # ---------------------------------
    # Trend
    # ---------------------------------
    df["trend"] = (df["sma_50"] > df["sma_200"]).astype(int)

    # ---------------------------------
    # Volatility
    # ---------------------------------
    df["vol_20"] = df["return_1"].rolling(20).std()

    # ---------------------------------
    # RSI (14)
    # ---------------------------------
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # ---------------------------------
    # Target (next-day direction)
    # ---------------------------------
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)

    # ---------------------------------
    # Cleanup
    # ---------------------------------
    df = df.dropna().reset_index(drop=True)

    return df
