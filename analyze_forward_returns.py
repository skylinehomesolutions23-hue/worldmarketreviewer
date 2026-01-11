import pandas as pd
import os

FILE = "data/forward_returns.csv"
OUTPUT = "results/forward_return_summary.csv"


def main():
    if not os.path.exists(FILE):
        raise RuntimeError(f"Missing file: {FILE}")

    df = pd.read_csv(FILE)

    if df.empty:
        raise RuntimeError("Forward returns file is empty")

    # Normalize columns
    df.columns = df.columns.str.strip().str.lower()

    required = {"rank", "forward_return"}
    if not required.issubset(df.columns):
        raise RuntimeError(f"Expected columns {required}, found {df.columns.tolist()}")

    summary = (
        df.groupby("rank")["forward_return"]
        .agg(
            count="count",
            mean_return="mean",
            median_return="median",
            win_rate=lambda x: (x > 0).mean(),
        )
        .reset_index()
        .sort_values("rank")
    )

    os.makedirs("results", exist_ok=True)
    summary.to_csv(OUTPUT, index=False)

    print(f"📊 Forward return analysis saved → {OUTPUT}")
    print(summary.head(10))


if __name__ == "__main__":
    main()
