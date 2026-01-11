import pandas as pd
from datetime import datetime

def log_results(results):
    df = pd.DataFrame(results)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    df.to_csv(f"signals_{ts}.csv", index=False)
