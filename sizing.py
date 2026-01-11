import pandas as pd
import numpy as np


def volatility_target_weights(
    prices: pd.DataFrame,
    target_vol: float = 0.15,
    lookback: int = 20,
    max_weight: float = 0.08,  # 👈 KEY CHANGE (8% cap)
):
    returns = prices.pct_change()
    vol = returns.rolling(lookback).std() * np.sqrt(252)

    raw_weights = target_vol / vol
    raw_weights = raw_weights.replace([np.inf, -np.inf], 0).fillna(0)

    # Normalize
    weights = raw_weights.div(raw_weights.sum(axis=1), axis=0)

    # Apply hard cap
    weights = weights.clip(upper=max_weight)

    # Re-normalize after cap
    weights = weights.div(weights.sum(axis=1), axis=0)

    return weights.fillna(0)
