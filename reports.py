import pandas as pd
from datetime import datetime


def save_results(results, filename="results_history.csv"):
    df = pd.DataFrame(results)
    df["timestamp"] = datetime.now()

    write_header = not pd.io.common.file_exists(filename)
    df.to_csv(filename, mode="a", header=write_header, index=False)
