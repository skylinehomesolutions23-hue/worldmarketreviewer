import pandas as pd
import numpy as np

def equity_curve(returns, capital=100_000):
    equity = (1 + returns).cumprod() * capital
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    return equity, drawdown
