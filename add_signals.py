import os
import pandas as pd

RESULTS_DIR = "results"
PRED_FILE = os.path.join(RESULTS_DIR, "predictions.csv")
SIGNALS_FILE = os.path.join(RESULTS_DIR, "signals.csv")

UP_THRESHOLD = 0.55
DOWN_THRESHOLD = 0.45

print("\n=== 🚦 SIGNAL CLASSIFICATION ===\n")

if not os.path.exists(PRED_FILE):
    raise FileNotFoundError("predictions.csv not found. Run main_autobatch.py first.")

df = pd.read_csv(PRED_FILE)

def classify(prob):
    if prob >= UP_THRESHOLD:
        return "UP"
    elif prob <= DOWN_THRESHOLD:
        return "DOWN"
    else:
        return "NEUTRAL"

df["signal"] = df["prob_up"].apply(classify)

df = df.sort_values("prob_up", ascending=False).reset_index(drop=True)

print(df)

# 🔒 SAVE TO DISK (THIS IS THE KEY PART)
df.to_csv(SIGNALS_FILE, index=False)

print(f"\n✅ Signals saved to {SIGNALS_FILE}")
