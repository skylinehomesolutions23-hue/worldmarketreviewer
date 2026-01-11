"""
Full end-to-end production pipeline runner.

This script:
1. Verifies live data integrity
2. Locks parameters (if manifest exists)
3. Runs the full backtest + risk + allocation stack
4. Produces final exposure curve

Any hard failure HALTS execution.
"""

import subprocess
import sys
from pathlib import Path

# ----------------------------
# STEP 1: LIVE DATA HEALTH
# ----------------------------
import live_data_health_check

print("🔍 Running live data health check...")
live_data_health_check.main()
print("✅ Data health check passed\n")

# ----------------------------
# STEP 2: PARAMETER LOCK (OPTIONAL BUT ENFORCED IF PRESENT)
# ----------------------------
try:
    import parameter_lock
    print("🔒 Checking parameter integrity...")
    parameter_lock.lock_parameters()
    print("✅ Parameters locked\n")
except FileNotFoundError:
    print("⚠️ parameter_manifest.json not found — skipping parameter lock\n")

# ----------------------------
# PIPELINE SEQUENCE
# ----------------------------
PIPELINE = [
    "final_master_backtest.py",
    "rolling_risk_diagnostics.py",
    "regime_conditional_risk_diagnostics.py",
    "rolling_distribution_stability.py",
    "tail_dependency_analysis.py",
    "integrated_risk_report.py",
    "capital_allocation_engine.py",
    "risk_kill_switch.py",
    "final_exposure_resolver.py",
]

BASE_DIR = Path(__file__).parent.resolve()


def run_script(script_name):
    script_path = BASE_DIR / script_name
    print(f"▶ Running: {script_name}")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"❌ Pipeline failed at {script_name}")


def main():
    print(f"Starting full pipeline from: {BASE_DIR}\n")

    for script in PIPELINE:
        run_script(script)
        print()

    print("✅ FULL PIPELINE COMPLETE")
    print("Final output:")
    print("results/final_exposure_curve.csv")


if __name__ == "__main__":
    main()
