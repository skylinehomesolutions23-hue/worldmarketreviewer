import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
DECAY_DIR = RESULTS_DIR / "decay"
DECAY_DIR.mkdir(parents=True, exist_ok=True)


def main():
    df = pd.read_csv(
        RESULTS_DIR / "signals_rank_filtered.csv",
        parse_dates=["date"]
    )

    # Lower rank = better signal
    TOP_N = 10
    df = df.sort_values(["date", "rank"])
    top = df.groupby("date").head(TOP_N)

    # Concentration: % of appearances by top 3 names
    counts = (
        top.groupby(["date", "ticker"])
        .size()
        .reset_index(name="count")
    )

    concentration = (
        counts.sort_values(["date", "count"], ascending=[True, False])
        .groupby("date")
        .head(3)
        .groupby("date")["count"]
        .sum()
        / TOP_N
    ).reset_index(name="top3_concentration")

    concentration.to_csv(
        DECAY_DIR / "signal_concentration.csv",
        index=False
    )

    print("✅ Signal concentration analysis complete")
    print(concentration.tail())


if __name__ == "__main__":
    main()
