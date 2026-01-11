import pandas as pd


def portfolio_equity_curve(trades):
    curves = []

    for t in trades:
        equity = (1 + t["returns"] * t["position"]).cumprod()
        curves.append(equity)

    portfolio = pd.concat(curves, axis=1).mean(axis=1)
    return portfolio
