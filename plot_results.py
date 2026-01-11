import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

EQUITY_FILE = Path("results/equity_curve.csv")


def main():
    df = pd.read_csv(EQUITY_FILE)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)

    df["equity"].plot(
        title="WorldMarketReviewer — Equity Curve",
        figsize=(10, 5),
        grid=True
    )

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
