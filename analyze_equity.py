import pandas as pd
import numpy as np
import sys

FILE = sys.argv[1] if len(sys.argv) > 1 else "results/portfolio_equity.csv"


def main():
    df = pd.read_csv(FILE)

    equity_col = "final_equity" if "final_equity" in df.columns else "equity"

    returns = df[equity_col].pct_change().dropna()

    years = len(returns) / 12
    cagr = (df[equity_col].iloc[-1] ** (1 / years)) - 1
    vol = returns.std() * np.sqrt(12)
    sharpe = cagr / vol if vol > 0 else 0

    drawdown = df[equity_col] / df[equity_col].cummax() - 1
    max_dd = drawdown.min()

    print(
        pd.DataFrame(
            {
                "CAGR": [round(cagr, 4)],
                "Sharpe": [round(sharpe, 4)],
                "Max Drawdown": [round(max_dd, 4)],
                "Total Return": [round(df[equity_col].iloc[-1], 4)],
            }
        )
    )


if __name__ == "__main__":
    main()
