import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
DECAY_DIR = RESULTS_DIR / "decay"
DECAY_DIR.mkdir(parents=True, exist_ok=True)

ROLLING_WINDOW = 36


def main():
    # Load signals and rename rank -> signal
    signals = (
        pd.read_csv(
            RESULTS_DIR / "signals_rank_filtered.csv",
            parse_dates=["date"]
        )
        .rename(columns={"rank": "signal"})
    )

    # Load forward returns (drop rank to avoid collision)
    fwd = (
        pd.read_csv(
            RESULTS_DIR / "forward_returns.csv",
            parse_dates=["date"]
        )
        .drop(columns=["rank"], errors="ignore")
    )

    # Merge datasets
    df = (
        signals
        .merge(fwd, on=["date", "ticker"], how="inner")
        .dropna(subset=["signal", "forward_return"])
        .sort_values("date")
    )

    # Hit = correct directional prediction
    df["hit"] = (df["signal"] * df["forward_return"]) > 0

    # Rolling hit rate by date
    hit_rate = (
        df.groupby("date")["hit"]
        .mean()
        .rolling(ROLLING_WINDOW)
        .mean()
        .reset_index()
        .rename(columns={"hit": "rolling_hit_rate"})
    )

    hit_rate.to_csv(DECAY_DIR / "signal_hit_rate.csv", index=False)

    print("✅ Signal hit rate analysis complete")
    print(hit_rate.tail())


if __name__ == "__main__":
    main()
