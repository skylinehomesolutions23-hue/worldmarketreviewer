# plot_rolling_top_bottom.py

import pandas as pd
import matplotlib.pyplot as plt
import os

INPUT_FILE = "results/rolling_rank_performance.csv"
OUTPUT_FILE = "results/plots/rolling_top_vs_bottom.png"


def main():
    df = pd.read_csv(INPUT_FILE, parse_dates=["date"])

    os.makedirs("results/plots", exist_ok=True)

    top_rank = df["rank"].min()
    bottom_rank = df["rank"].max()

    top = df[df["rank"] == top_rank]
    bottom = df[df["rank"] == bottom_rank]

    plt.figure()
    plt.plot(top["date"], top["rolling_mean_return"], label=f"Rank {top_rank}")
    plt.plot(bottom["date"], bottom["rolling_mean_return"], label=f"Rank {bottom_rank}")
    plt.axhline(0)
    plt.legend()
    plt.title("Rolling 5Y Mean Forward Return: Top vs Bottom")
    plt.savefig(OUTPUT_FILE)
    plt.close()

    print("📊 Rolling top vs bottom plot saved → results/plots/")


if __name__ == "__main__":
    main()
