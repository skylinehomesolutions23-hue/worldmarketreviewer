import pandas as pd
import matplotlib.pyplot as plt
from config import RESULTS_DIR


def main():
    equity = pd.read_csv(
        RESULTS_DIR / "equity_curve_monthly.csv",
        parse_dates=["date"]
    )

    regime = pd.read_csv(
        RESULTS_DIR / "regime_monthly.csv",
        parse_dates=["date"]
    )

    plt.figure()
    plt.plot(equity["date"], equity["equity"])
    plt.title("Monthly Momentum Strategy (Top 10 + Risk-Off)")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.show()


if __name__ == "__main__":
    main()
