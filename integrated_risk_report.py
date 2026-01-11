import pandas as pd
from pathlib import Path


# -----------------------------
# Paths
# -----------------------------

RESULTS_DIR = Path("results")
DIAG_DIR = RESULTS_DIR / "diagnostics"

ROLLING_RISK = DIAG_DIR / "rolling_risk_diagnostics.csv"
REGIME_RISK = DIAG_DIR / "regime_conditional_risk.csv"
TAIL_RISK = DIAG_DIR / "tail_dependency_summary.csv"
DIST_STAB = DIAG_DIR / "rolling_distribution_stability.csv"

OUT_PATH = RESULTS_DIR / "integrated_risk_report.csv"


# -----------------------------
# Main
# -----------------------------

def main():
    sections = []

    # Rolling risk (latest row only)
    if ROLLING_RISK.exists():
        rolling = pd.read_csv(ROLLING_RISK, index_col=0, parse_dates=True)
        latest = rolling.iloc[-1].to_frame(name="latest").T
        latest["section"] = "rolling_risk_latest"
        sections.append(latest.reset_index(drop=True))

    # Regime conditional
    if REGIME_RISK.exists():
        regime = pd.read_csv(REGIME_RISK)
        regime["section"] = "regime_conditional"
        sections.append(regime)

    # Tail dependency
    if TAIL_RISK.exists():
        tail = pd.read_csv(TAIL_RISK)
        tail["section"] = "tail_dependency"
        sections.append(tail)

    # Distribution stability (summary)
    if DIST_STAB.exists():
        dist = pd.read_csv(DIST_STAB)
        summary = dist.mean(numeric_only=True).to_frame(name="avg").T
        summary["section"] = "distribution_stability"
        sections.append(summary)

    if not sections:
        raise RuntimeError("No diagnostics found to aggregate")

    report = pd.concat(sections, axis=0, ignore_index=True)
    report.to_csv(OUT_PATH, index=False)

    print("Integrated risk report created.")
    print(f"Saved to: {OUT_PATH}")


if __name__ == "__main__":
    main()
