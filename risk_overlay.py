import pandas as pd
from pathlib import Path

# -----------------------------
# Cross-platform paths
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"

RETURNS_FILE = RESULTS_DIR / "monthly_returns.csv"
RISK_FILE = RESULTS_DIR / "integrated_risk_report.csv"
OUTPUT_FILE = RESULTS_DIR / "portfolio_returns_with_risk_overlay.csv"


def load_returns(path: Path) -> pd.DataFrame:
    """Load returns and intelligently handle date column"""
    df = pd.read_csv(path)

    if df.empty:
        raise ValueError("monthly_returns.csv is empty")

    # Normalize date column
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    elif "month" in df.columns:
        df["date"] = pd.to_datetime(df["month"])
    elif "period" in df.columns:
        df["date"] = pd.to_datetime(df["period"])
    else:
        # last resort: treat index as date-like
        df = df.reset_index(drop=False)
        df.rename(columns={df.columns[0]: "date"}, inplace=True)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df


def main():
    # -----------------------------
    # File existence checks
    # -----------------------------
    if not RETURNS_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {RETURNS_FILE}")

    if not RISK_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {RISK_FILE}")

    # -----------------------------
    # Load data
    # -----------------------------
    returns = load_returns(RETURNS_FILE)
    risk = pd.read_csv(RISK_FILE)

    # -----------------------------
    # Risk metric selection
    # -----------------------------
    risk_cols = [
        "beta_3m", "vol_3m", "max_dd_3m",
        "beta_6m", "vol_6m", "max_dd_6m",
        "beta_12m", "vol_12m", "max_dd_12m",
        "portfolio_tail_max_dd"
    ]

    available_risk_cols = [c for c in risk_cols if c in risk.columns]

    if not available_risk_cols:
        raise ValueError("No usable risk columns found in integrated_risk_report.csv")

    # Most recent risk snapshot
    risk_snapshot = risk.iloc[-1][available_risk_cols]

    # -----------------------------
    # Apply overlay
    # -----------------------------
    for col in available_risk_cols:
        returns[col] = risk_snapshot[col]

    # Optional but useful metric
    if "gross_return" in returns.columns and "vol_3m" in returns.columns:
        returns["risk_adjusted_return"] = (
            returns["gross_return"] / returns["vol_3m"]
        )

    # -----------------------------
    # Save output
    # -----------------------------
    returns.to_csv(OUTPUT_FILE, index=False)

    print("✅ Risk overlay applied successfully")
    print(f"📄 Output written to: {OUTPUT_FILE}")
    print(returns.tail())


if __name__ == "__main__":
    main()
