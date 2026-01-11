import pandas as pd
from datetime import datetime

def export_results(rankings, weights):
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    pd.DataFrame(rankings).to_csv(f"ranking_{ts}.csv")
    weights.to_csv(f"portfolio_{ts}.csv")

    print(f"📁 Exported ranking_{ts}.csv and portfolio_{ts}.csv")
