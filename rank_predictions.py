import pandas as pd

df = pd.read_csv("results/predictions.csv")

df = df.sort_values("prob_up", ascending=False).reset_index(drop=True)

print("\n=== 📊 RANKED STOCK LEADERBOARD ===\n")
print(df)

df.to_csv("results/predictions_ranked.csv", index=False)
