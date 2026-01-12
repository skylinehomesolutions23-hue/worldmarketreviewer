# main_autobatch_phase2.py
import os
import time
import argparse
from datetime import datetime

import pandas as pd

from data_loader import load_stock_data
from feature_engineering import build_features
from walk_forward import walk_forward_predict_proba

from phase2_state import (
    load_state, save_state,
    mark_started, mark_success, mark_failed,
    should_run, reset_ticker
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
DEFAULT_RESULTS_FILE = os.path.join(RESULTS_DIR, "predictions.csv")
DEFAULT_STATE_FILE = os.path.join(BASE_DIR, "phase2_state.json")
os.makedirs(RESULTS_DIR, exist_ok=True)

TICKERS_DEFAULT = [
    "AMZN","META","TSLA","NVDA","NFLX","AMD","INTC","JPM","BAC","GS",
    "MS","XOM","CVX","SPY","QQQ","DIA","ORCL","IBM","CRM","ADBE",
    "WMT","COST","HD","PFE","JNJ","UNH","BA","CAT","GE","XLK","XLF",
    "XLE","XLV","XLI","XLY","XLP","XLU"
]


def upsert_latest_result(results_file: str, row: dict) -> None:
    """
    Keep ONE latest row per ticker in results/predictions.csv.
    Also avoids pandas concat warning by ensuring consistent columns.
    """
    cols = ["ticker", "prob_up", "direction", "run_id", "asof", "status"]

    if os.path.exists(results_file):
        df = pd.read_csv(results_file)
        for c in cols:
            if c not in df.columns:
                df[c] = None
        df = df[cols]
    else:
        df = pd.DataFrame(columns=cols)

    # drop old and append
    df = df[df["ticker"] != row["ticker"]]
    df.loc[len(df)] = {c: row.get(c, None) for c in cols}
    df.to_csv(results_file, index=False)


def parse_args():
    p = argparse.ArgumentParser(description="Phase 2 runner (monthly_prices.csv + state file).")

    group = p.add_mutually_exclusive_group(required=False)
    group.add_argument("--all", action="store_true", help="Run the default ticker list.")
    group.add_argument("--ticker", type=str, help="Run a single ticker, e.g. AMZN.")
    group.add_argument("--tickers", type=str, help="Comma list, e.g. AMZN,TSLA,NVDA.")

    p.add_argument("--force", action="store_true", help="Run even if state says success.")
    p.add_argument("--reset", type=str, help="Reset state for ticker (e.g. AMZN) then exit.")
    p.add_argument("--state-file", type=str, default=DEFAULT_STATE_FILE, help="Path to state JSON.")
    p.add_argument("--results-file", type=str, default=DEFAULT_RESULTS_FILE, help="Path to predictions CSV.")
    p.add_argument("--sleep", type=float, default=0.0, help="Sleep between tickers (seconds). Use 0 to disable.")

    return p.parse_args()


def main():
    # Force UTF-8 output if possible (helps on Windows terminals)
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    args = parse_args()

    if args.reset:
        state = load_state(args.state_file)
        reset_ticker(state, args.reset.upper().strip())
        save_state(args.state_file, state)
        print(f"Reset state for {args.reset.upper().strip()} in {args.state_file}")
        return

    if args.ticker:
        tickers = [args.ticker.upper().strip()]
    elif args.tickers:
        tickers = [t.upper().strip() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = TICKERS_DEFAULT

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    state = load_state(args.state_file)

    print("\n=== PHASE 2 STARTED ===")
    print(f"Run ID:  {run_id}")
    print(f"State:   {args.state_file}")
    print(f"Output:  {args.results_file}")
    print("Tickers: " + ", ".join(tickers))
    print()

    for i, ticker in enumerate(tickers, start=1):
        if not should_run(state, ticker, force=args.force):
            print(f"[SKIP] {ticker} (state=success). Use --force to rerun.")
            continue

        print(f"[{i}/{len(tickers)}] Running: {ticker}")
        mark_started(state, ticker, run_id)
        save_state(args.state_file, state)

        try:
            df = load_stock_data(ticker)
            if df is None or len(df) < 10:
                raise ValueError("Not enough data loaded from monthly_prices.csv")

            df = build_features(df)
            feature_cols = [c for c in df.columns if c not in ["target", "date"]]

            probs = walk_forward_predict_proba(
                df,
                feature_cols=feature_cols,
                target_col="target",
            )

            prob_up = float(probs.iloc[-1])
            direction = "UP" if prob_up >= 0.5 else "DOWN"

            row = {
                "ticker": ticker,
                "prob_up": prob_up,
                "direction": direction,
                "run_id": run_id,
                "asof": datetime.now().isoformat(timespec="seconds"),
                "status": "success"
            }
            upsert_latest_result(args.results_file, row)

            mark_success(state, ticker, run_id)
            save_state(args.state_file, state)

            print(f"OK {ticker}: {direction} ({prob_up:.2%})")

            if args.sleep and args.sleep > 0:
                time.sleep(args.sleep)

        except Exception as e:
            err = str(e)
            row = {
                "ticker": ticker,
                "prob_up": None,
                "direction": None,
                "run_id": run_id,
                "asof": datetime.now().isoformat(timespec="seconds"),
                "status": f"failed: {err}"
            }
            upsert_latest_result(args.results_file, row)

            mark_failed(state, ticker, run_id, err)
            save_state(args.state_file, state)

            print(f"FAIL {ticker}: {err}")

    print("\n=== PHASE 2 COMPLETE ===")
    print(f"Results: {args.results_file}")
    print(f"State:   {args.state_file}")


if __name__ == "__main__":
    main()
