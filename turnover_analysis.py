import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
DECAY_DIR = RESULTS_DIR / "decay"
DECAY_DIR.mkdir(parents=True, exist_ok=True)

TOP_N = 10
ROLLING_WINDOW = 12


def main():
    df = pd.read_csv(
        RESULTS_DIR / "signals_rank_filtered.csv",
        parse_dates=["date"]
    )

    # Ensure proper sorting
    df = df.sort_values(["date", "rank"])

    # Take top N per date (explicit copy to avoid SettingWithCopyWarning)
    top = df.groupby("date").head(TOP_N).copy()

    # Previous rank per ticker
    top["prev_rank"] = top.groupby("ticker")["rank"].shift(1)

    # Turnover: rank change indicator
    top["turnover"] = (top["rank"] != top["prev_rank"]).astype(int)

    # Aggregate turnover by date
    turnover = (
        top.groupby("date")["turnover"]
        .mean()
        .reset_index()
    )

    # Rolling turnover
    turnover["rolling_turnover"] = (
        turnover["turnover"]
        .rolling(ROLLING_WINDOW, min_periods=6)
        .mean()
    )

    # Save
    out = DECAY_DIR / "turnover.csv"
    turnover.to_csv(out, index=False)

    print("✅ Turnover analysis complete")
    print(turnover.tail())


if __name__ == "__main__":
    main()
