# metrics.py

import numpy as np
import pandas as pd


def compute_metrics(equity: pd.Series, trades: pd.Series | None = None):
    """
    equity: Series indexed by date
    trades: optional Series of per-trade PnL
    """

    returns = equity.pct_change().dropna()

    sharpe = np.nan
    if returns.std() != 0:
        sharpe = returns.mean() / returns.std() * np.sqrt(252)

    cum = (1 + returns).cumprod()
    drawdown = cum / cum.cummax() - 1
    max_dd = drawdown.min()

    win_rate = np.nan
    if trades is not None and len(trades) > 0:
        win_rate = (trades > 0).mean()

    return {
        "CAGR": (equity.iloc[-1] / equity.iloc[0]) ** (252 / len(returns)) - 1,
        "Sharpe": sharpe,
        "MaxDrawdown": max_dd,
        "WinRate": win_rate,
    }
