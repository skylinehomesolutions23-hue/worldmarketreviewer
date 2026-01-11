import pandas as pd
from pathlib import Path

DATA_DIR = Path("results")
DECAY_DIR = DATA_DIR / "decay"
DECAY_DIR.mkdir(parents=True, exist_ok=True)

TOP_N = 10
TCOST_PER_TURNOVER = 0.001  # 10 bps
ROLLING_WINDOW = 12


def main():
    # Load ranked signals
    signals = pd.read_csv(
        DATA_DIR / "signals_rank_filtered.csv",
        parse_dates=["date"]
    )

    # Load forward returns
    returns = pd.read_csv(
        DATA_DIR / "forward_returns.csv",
        parse_dates=["date"]
    )

    signals = signals.sort_values(["date", "rank"])

    # Build Top-N portfolio
    portfolio = (
        signals.groupby("date")
        .head(TOP_N)
        .loc[:, ["date", "ticker"]]
    )

    # Position matrix
    positions = (
        portfolio.assign(weight=1)
        .pivot(index="date", columns="ticker", values="weight")
        .fillna(0)
        .sort_index()
    )

    positions = positions.div(positions.sum(axis=1), axis=0)

    # Align returns
    returns = (
        returns.set_index(["date", "ticker"])["forward_return"]
        .unstack("ticker")
        .reindex(positions.index)
        .fillna(0)
    )

    # Gross portfolio returns
    gross_return = (positions * returns).sum(axis=1)

    # Turnover
    turnover = positions.diff().abs().sum(axis=1) / 2
    trading_cost = turnover * TCOST_PER_TURNOVER

    # Net returns
    net_return = gross_return - trading_cost

    result = pd.DataFrame({
        "date": gross_return.index,
        "gross_return": gross_return.values,
        "net_return": net_return.values,
        "turnover": turnover.values,
        "trading_cost": trading_cost.values
    })

    # Rolling metrics
    result["rolling_gross"] = result["gross_return"].rolling(ROLLING_WINDOW).mean()
    result["rolling_net"] = result["net_return"].rolling(ROLLING_WINDOW).mean()

    # Save
    out_path = DECAY_DIR / "portfolio_returns.csv"
    result.to_csv(out_path, index=False)

    print("✅ Portfolio return analysis complete")
    print(result.tail())


if __name__ == "__main__":
    main()
