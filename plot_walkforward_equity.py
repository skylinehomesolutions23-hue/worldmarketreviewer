import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

RESULTS_DIR = Path("results")

def main():
    df = pd.read_csv(RESULTS_DIR / "walkforward_equity.csv")
    df["month"] = pd.to_datetime(df["month"])

    df["peak"] = df["equity"].cummax()
    df["drawdown"] = (df["equity"] - df["peak"]) / df["peak"]

    plt.figure()
    plt.plot(df["month"], df["equity"])
    plt.title("Walk-Forward Monthly Equity Curve")
    plt.xlabel("Month")
    plt.ylabel("Equity")
    plt.show()

    plt.figure()
    plt.plot(df["month"], df["drawdown"])
    plt.title("Walk-Forward Drawdown")
    plt.xlabel("Month")
    plt.ylabel("Drawdown")
    plt.show()

if __name__ == "__main__":
    main()
