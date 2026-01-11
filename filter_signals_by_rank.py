# filter_signals_by_rank.py
import pandas as pd

SIGNALS_FILE = "data/signals.csv"
RANK_FILE = "data/good_ranks.csv"
OUT_FILE = "data/signals_rank_filtered.csv"

def main():
    sig = pd.read_csv(SIGNALS_FILE)
    ranks = pd.read_csv(RANK_FILE)

    sig = sig[sig["rank"].isin(ranks["rank"])]

    sig.to_csv(OUT_FILE, index=False)

    print("✅ Rank-filtered signals saved →", OUT_FILE)
    print(sig.head())

if __name__ == "__main__":
    main()
