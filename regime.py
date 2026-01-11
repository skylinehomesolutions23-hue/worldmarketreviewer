import pandas as pd


def compute_regime(spy_df: pd.DataFrame, lookback: int = 200) -> pd.Series:
    """
    Risk-on if SPY close > SMA(lookback)
    """
    spy_df = spy_df.sort_values("date").copy()
    spy_df["sma"] = spy_df["close"].rolling(lookback).mean()
    regime = spy_df["close"] > spy_df["sma"]
    regime.name = "risk_on"
    return regime
