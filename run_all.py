# run_all.py
import subprocess
import sys

SCRIPTS = [
    "rank_stability_analysis.py",
    "portfolio_breadth_analysis.py",
    "turnover_analysis.py",
    "signal_concentration_analysis.py",
    "regime_signal_consistency.py",
    "portfolio_returns.py",
    "performance_attribution.py",
    "risk_metrics.py",
    "risk_overlay.py",
    "signal_auto_kill_v3.py",
    "strategy_health_report.py",
]

def main():
    for script in SCRIPTS:
        print(f"\n▶ Running {script}")
        result = subprocess.run([sys.executable, script])
        if result.returncode != 0:
            print(f"❌ Failed at {script}")
            sys.exit(1)

    print("\n✅ FULL PIPELINE COMPLETE")

if __name__ == "__main__":
    main()
