# rank_filter.py
import pandas as pd

SUMMARY_FILE = "results/forward_return_summary.csv"
OUT_FILE = "data/good_ranks.csv"

def main():
    df = pd.read_csv(SUMMARY_FILE)

    # Keep ranks with positive mean return
    good = df[df["mean_return"] > 0].copy()

    good[["rank"]].to_csv(OUT_FILE, index=False)

    print("✅ Good ranks saved →", OUT_FILE)
    print(good)

if __name__ == "__main__":
    main()
