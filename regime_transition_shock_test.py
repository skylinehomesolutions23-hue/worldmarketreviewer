import pandas as pd
from pathlib import Path

EQUITY_PATH = Path("results/portfolio_equity_FINAL.csv")
REGIME_PATH = Path("results/regime_monthly.csv")
OUT_PATH = Path("results/regime_transition_shocks.csv")

WINDOW = 3  # months before/after


def main():
    equity = pd.read_csv(EQUITY_PATH, index_col=0, parse_dates=True)
    regime = pd.read_csv(REGIME_PATH, index_col=0, parse_dates=True)

    eq = equity.iloc[:, 0]
    reg = regime.iloc[:, 0]

    transitions = reg[reg != reg.shift()].dropna()

    results = []

    for date in transitions.index:
        start = date - pd.DateOffset(months=WINDOW)
        end = date + pd.DateOffset(months=WINDOW)

        price_window = eq.loc[start:end]

        # 🔒 GUARD: need at least 2 points to compute returns
        if len(price_window) < 2:
            continue

        returns = price_window.pct_change().dropna()
        if returns.empty:
            continue

        cum = (1 + returns).cumprod()

        results.append({
            "transition_date": date,
            "window_return": cum.iloc[-1] - 1,
            "window_vol": returns.std() * (12 ** 0.5),
            "window_max_dd": (cum / cum.cummax() - 1).min()
        })

    out = pd.DataFrame(results)

    if out.empty:
        print("No valid regime transition windows found.")
        return

    out.to_csv(OUT_PATH, index=False)

    print("Regime transition shock test complete.")
    print(out.sort_values("window_max_dd").head(3))


if __name__ == "__main__":
    main()
