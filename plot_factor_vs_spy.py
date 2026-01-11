# plot_factor_vs_spy.py

import pandas as pd
import matplotlib.pyplot as plt

FILE = "results/benchmark_comparison.csv"
OUTPUT = "results/plots/factor_vs_spy.png"


def main():
    df = pd.read_csv(FILE, parse_dates=["date"])

    if df.empty:
        raise RuntimeError("Benchmark comparison file is empty")

    plt.figure(figsize=(10, 6))
    plt.plot(df["date"], df["equity"], label="Factor Strategy")
    plt.plot(df["date"], df["spy_equity"], label="SPY Buy & Hold")

    plt.title("Factor Strategy vs SPY")
    plt.xlabel("Date")
    plt.ylabel("Equity (Growth of $1)")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.savefig(OUTPUT)
    plt.close()

    print("📈 Factor vs SPY plot saved →", OUTPUT)


if __name__ == "__main__":
    main()
