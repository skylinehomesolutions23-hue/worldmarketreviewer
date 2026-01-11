import pandas as pd
from pathlib import Path

DATA_DIR = Path("results")
DECAY_DIR = DATA_DIR / "decay"
DECAY_DIR.mkdir(parents=True, exist_ok=True)

TOP_N = 10


def main():
    signals = pd.read_csv(
        DATA_DIR / "signals_rank_filtered.csv",
        parse_dates=["date"]
    )

    returns = pd.read_csv(
        DATA_DIR / "forward_returns.csv",
        parse_dates=["date"]
    )

    df = signals.merge(
        returns[["date", "ticker", "forward_return"]],
        on=["date", "ticker"],
        how="inner"
    )

    df = df.sort_values(["date", "rank"])

    top = df.groupby("date").head(TOP_N)
    bottom = df.groupby("date").tail(TOP_N)

    result = pd.DataFrame({
        "date": top["date"].unique(),
        "top_return": top.groupby("date")["forward_return"].mean().values,
        "bottom_return": bottom.groupby("date")["forward_return"].mean().values
    })

    result["spread"] = result["top_return"] - result["bottom_return"]
    result["rolling_spread"] = result["spread"].rolling(12).mean()

    out = DECAY_DIR / "performance_attribution.csv"
    result.to_csv(out, index=False)

    print("✅ Performance attribution complete")
    print(result.tail())


if __name__ == "__main__":
    main()
