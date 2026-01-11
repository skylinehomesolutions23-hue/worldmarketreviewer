from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
from pathlib import Path
import math

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).resolve().parent
SUMMARY_FILE = BASE_DIR / "results" / "mobile_summary.csv"


def safe_value(v):
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
    return v


def load_summary():
    print("Looking for:", SUMMARY_FILE)
    print("Exists?", SUMMARY_FILE.exists())

    if not SUMMARY_FILE.exists():
        return {"error": "summary file not found"}

    try:
        df = pd.read_csv(SUMMARY_FILE)

        if df.empty:
            return {"error": "summary file empty"}

        df = df.fillna("")

        records = []
        for _, row in df.iterrows():
            clean = {k: safe_value(v) for k, v in row.to_dict().items()}
            records.append(clean)

        return records

    except Exception as e:
        return {"error": str(e)}


@app.route("/api/summary")
def api_summary():
    return jsonify(load_summary())


@app.route("/")
def root():
    return jsonify({"status": "API running"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
