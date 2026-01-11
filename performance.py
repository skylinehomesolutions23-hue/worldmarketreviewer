import numpy as np
import pandas as pd

def performance_report(returns: pd.Series):
    returns = returns.dropna()

    if returns.std() == 0:
        return {
            "Sharpe": 0.0,
            "CAGR": 0.0,
            "Max DD": 0.0,
            "Win Rate": 0.0
        }

    sharpe = np.sqrt(252) * returns.mean() / returns.std()

    cum = (1 + returns).cumprod()
    years = len(returns) / 252
    cagr = cum.iloc[-1] ** (1 / years) - 1

    drawdown = (cum / cum.cummax() - 1).min()

    win_rate = (returns > 0).mean()

    return {
        "Sharpe": round(sharpe, 2),
        "CAGR": round(cagr * 100, 2),
        "Max DD": round(drawdown * 100, 2),
        "Win Rate": round(win_rate * 100, 2)
    }
