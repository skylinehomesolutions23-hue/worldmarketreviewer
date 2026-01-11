# run_monthly_full_history.py
import subprocess
from pathlib import Path
from run_monthly_history import list_available_months

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def month_already_done(month: str) -> bool:
    file = OUTPUT_DIR / f"signals_{month.replace('-', '_')}.csv"
    return file.exists()


def main():
    months = list_available_months()
    print(f"📆 Found {len(months)} months")

    for month in months:
        if month_already_done(month):
            print(f"⏩ Skipping {month} (already processed)")
            continue

        print(f"▶ Running {month}")
        subprocess.run(
            [str(PYTHON), "backtest_monthly.py", f"{month}-28"],
            check=True
        )

    print("✅ Full monthly history complete")


if __name__ == "__main__":
    main()
