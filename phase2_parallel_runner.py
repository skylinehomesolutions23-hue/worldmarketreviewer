import os
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TICKERS_DEFAULT = [
    "AMZN","META","TSLA","NVDA","NFLX","AMD","INTC","JPM","BAC","GS",
    "MS","XOM","CVX","SPY","QQQ","DIA","ORCL","IBM","CRM","ADBE",
    "WMT","COST","HD","PFE","JNJ","UNH","BA","CAT","GE","XLK","XLF",
    "XLE","XLV","XLI","XLY","XLP","XLU"
]


def run_one(ticker: str, force: bool, sleep: float) -> tuple[str, int, str]:
    ticker = ticker.upper().strip()
    runner = os.path.join(BASE_DIR, "main_autobatch_phase2.py")

    cmd = [sys.executable, runner, "--ticker", ticker, "--sleep", str(sleep)]
    if force:
        cmd.append("--force")

    env = os.environ.copy()
    # Force UTF-8 for child processes (Windows-safe)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    p = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    out_lines = []
    for line in p.stdout:
        out_lines.append(line.rstrip("\n"))
    p.wait()

    return ticker, p.returncode, "\n".join(out_lines)


def parse_args():
    p = argparse.ArgumentParser(description="Parallel Phase 2 runner (server/mobile-friendly).")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run the default ticker list.")
    group.add_argument("--tickers", type=str, help="Comma list, e.g. AMZN,TSLA,NVDA.")

    p.add_argument("--max-parallel", type=int, default=4, help="How many tickers to run concurrently.")
    p.add_argument("--force", action="store_true", help="Force rerun even if state says success.")
    p.add_argument("--sleep", type=float, default=0.0, help="Sleep inside each single-ticker run.")
    return p.parse_args()


def main():
    args = parse_args()

    if args.all:
        tickers = TICKERS_DEFAULT
    else:
        tickers = [t.upper().strip() for t in args.tickers.split(",") if t.strip()]

    max_parallel = max(1, int(args.max_parallel))

    print("=== Phase 2 Parallel Runner ===")
    print(f"Tickers: {len(tickers)}")
    print(f"MaxParallel: {max_parallel}")
    print(f"Force: {args.force}")
    print()

    results = []
    with ThreadPoolExecutor(max_workers=max_parallel) as ex:
        future_map = {ex.submit(run_one, t, args.force, args.sleep): t for t in tickers}
        for fut in as_completed(future_map):
            t = future_map[fut]
            try:
                ticker, code, output = fut.result()
                results.append((ticker, code))
                print(f"\n--- {ticker} (exit={code}) ---")
                print(output)
            except Exception as e:
                results.append((t, 1))
                print(f"\n--- {t} (EXCEPTION) ---")
                print(str(e))

    ok = sum(1 for _, c in results if c == 0)
    bad = sum(1 for _, c in results if c != 0)
    print("\n=== DONE ===")
    print(f"Success: {ok}  Failed: {bad}")

    raise SystemExit(0 if bad == 0 else 1)


if __name__ == "__main__":
    main()
