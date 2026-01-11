# plot_factor_equity.py

import pandas as pd
import matplotlib.pyplot as plt
import os

INPUT_FILE = "results/factor_equity.csv"
OUTPUT_FILE = "results/plots/factor_equity.png"


def main():
    df = pd.read_csv(INPUT_FILE, parse_dates=["date"])

    os.makedirs("results/plots", exist_ok=True)

    plt.figure()
    plt.plot(df["date"], df["equity"])
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.title("Factor Equity Curve")
    plt.savefig(OUTPUT_FILE)
    plt.close()

    print("📈 Factor equity plot saved → results/plots/factor_equity.png")


if __name__ == "__main__":
    main()
