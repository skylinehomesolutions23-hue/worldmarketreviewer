# cost_stress_test.py

import pandas as pd

SIGNALS_FILE = "data/signals.csv"
RETURNS_FILE = "data/forward_returns.csv"
BASE_COST = 0.001  # 10 bps
OUT_FILE = "results/cost_stress_test.csv"


def detect_rank_column(df):
    for col in df.columns:
        if "rank" in col.lower():
            return col
    raise ValueError(f"No rank column found in signals.csv: {df.columns.tolist()}")


def detect_return_column(df):
    for col in df.columns:
        if "ret" in col.lower():
            return col
    raise ValueError(f"No return column found in returns file: {df.columns.tolist()}")

def run(cost):
    sig = pd.read_csv(SIGNALS_FILE, parse_dates=["date"])
    ret = pd.read_csv(RETURNS_FILE, parse_dates=["date"])

    rank_col = detect_rank_column(sig)
    ret_col = detect_return_column(ret)

    # 🔒 Lock column names BEFORE merge
    sig = sig.rename(columns={rank_col: "signal_rank"})
    ret = ret.rename(columns={ret_col: "asset_ret"})

    df = sig.merge(ret, on=["date", "ticker"], how="left")
    df["asset_ret"] = df["asset_ret"].fillna(0)

    df = df.sort_values(["ticker", "date"])

    # Cross-sectional weights
    max_rank = df.groupby("date")["signal_rank"].transform("max")
    df["weight"] = (max_rank - df["signal_rank"] + 1) / max_rank

    # Turnover
    df["turnover"] = (
        df.groupby("ticker")["weight"]
        .diff()
        .abs()
        .fillna(df["weight"].abs())
    )

    df["net_ret"] = df["asset_ret"] * df["weight"] - df["turnover"] * cost

    monthly = df.groupby("date")["net_ret"].mean()
    equity = (1 + monthly).cumprod()

    return equity



def main():
    results = pd.DataFrame()

    scenarios = {
        "base_cost": 1.0,
        "cost_1.5x": 1.5,
        "cost_2.0x": 2.0,
    }

    for label, mult in scenarios.items():
        eq = run(BASE_COST * mult)
        results[label] = eq / eq.iloc[0]

    results.to_csv(OUT_FILE)
    print(f"📉 Cost stress results saved → {OUT_FILE}")
    print(results.tail())


if __name__ == "__main__":
    main()
