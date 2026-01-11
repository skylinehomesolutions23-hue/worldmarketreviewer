import pandas as pd
import numpy as np
from pathlib import Path

RESULTS_DIR = Path("results")


def main():
    file = RESULTS_DIR / "equity_vs_spy.csv"

    if not file.exists():
        raise FileNotFoundError("equity_vs_spy.csv not found")

    df = pd.read_csv(file)

    if len(df) < 3:
        raise ValueError("Not enough data for alpha/beta")

    df["strategy_ret"] = df["equity"].pct_change()
    df["spy_ret"] = df["spy_equity"].pct_change()

    df = df.dropna()

    if df.empty:
        raise ValueError("No overlapping returns")

    beta = np.cov(df["strategy_ret"], df["spy_ret"])[0, 1] / np.var(df["spy_ret"])
    alpha = (df["strategy_ret"].mean() - beta * df["spy_ret"].mean()) * 12

    result = pd.DataFrame(
        {
            "Alpha (annualized)": [round(alpha, 4)],
            "Beta": [round(beta, 4)],
        }
    )

    out = RESULTS_DIR / "alpha_beta.csv"
    result.to_csv(out, index=False)

    print("📈 Alpha/Beta saved →", out)
    print(result)


if __name__ == "__main__":
    main()
