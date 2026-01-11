# run_monthly.py
import argparse
import subprocess
import sys
from utils_dates import latest_available_month, parse_month

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", type=str, help="YYYY-MM")
    args = parser.parse_args()

    if args.month:
        end_date = parse_month(args.month)
        print(f"📅 Running for {end_date.date()}")
    else:
        end_date = latest_available_month()
        print(f"📅 Running latest available month: {end_date.date()}")

    subprocess.run(
        [sys.executable, "backtest_monthly.py", str(end_date.date())],
        check=True
    )

    subprocess.run([sys.executable, "analyze_equity_monthly.py"], check=True)
    subprocess.run([sys.executable, "plot_results_monthly.py"], check=True)

if __name__ == "__main__":
    main()
