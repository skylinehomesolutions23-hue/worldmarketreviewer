import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
OUT_DIR = RESULTS_DIR / "portfolio_diagnostics"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOP_K = 10


def main():
    signals = pd.read_csv(
        RESULTS_DIR / "signals_rank_filtered.csv",
        parse_dates=["date"]
    )

    fwd = pd.read_csv(
        RESULTS_DIR / "forward_returns.csv",
        parse_dates=["date"]
    )

    # ⚠️ Drop rank from forward returns to avoid collision
    fwd = fwd.drop(columns=["rank"], errors="ignore")

    df = signals.merge(
        fwd,
        on=["date", "ticker"],
        how="inner"
    )

    # Use SIGNAL rank only
    df = df.sort_values(["date", "rank"])
    df = df.groupby("date").head(TOP_K)

    df["contribution"] = df["forward_return"]

    breadth = (
        df.groupby("date")
        .size()
        .reset_index(name="active_names")
    )

    breadth["rolling_breadth"] = (
        breadth["active_names"]
        .rolling(12)
        .mean()
    )

    breadth.to_csv(
        OUT_DIR / "portfolio_breadth.csv",
        index=False
    )

    print("✅ Portfolio breadth analysis complete")
    print(breadth.tail())


if __name__ == "__main__":
    main()
