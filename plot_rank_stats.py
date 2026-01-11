# plot_rank_stats.py

import pandas as pd
import matplotlib.pyplot as plt
import os

INPUT_FILE = "results/forward_return_summary.csv"
OUTPUT_DIR = "results/plots"


def main():
    df = pd.read_csv(INPUT_FILE)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---- Mean return by rank ----
    plt.figure()
    plt.bar(df["rank"], df["mean_return"])
    plt.xlabel("Rank")
    plt.ylabel("Mean Forward Return")
    plt.title("Mean Forward Return by Rank")
    plt.savefig(f"{OUTPUT_DIR}/mean_return_by_rank.png")
    plt.close()

    # ---- Win rate by rank ----
    plt.figure()
    plt.bar(df["rank"], df["win_rate"])
    plt.xlabel("Rank")
    plt.ylabel("Win Rate")
    plt.title("Win Rate by Rank")
    plt.axhline(0.5)
    plt.savefig(f"{OUTPUT_DIR}/win_rate_by_rank.png")
    plt.close()

    print("📊 Rank plots saved → results/plots/")


if __name__ == "__main__":
    main()
