import pandas as pd
from pathlib import Path
from data_registry import classify_file

DATA_DIR = Path("data")

EXTREME_RETURN_LIMIT = 5.0  # 500% — only for PRICE


def inspect_file(path: Path):
    file_type = classify_file(path)

    try:
        df = pd.read_csv(path)
    except Exception as e:
        return {
            "dataset": path.name,
            "rows": 0,
            "issues": f"READ_ERROR: {e}",
            "status": "FAIL",
        }

    if df.empty:
        return {
            "dataset": path.name,
            "rows": 0,
            "issues": "EMPTY_FILE",
            "status": "FAIL" if file_type == "PRICE" else "WARN",
        }

    issues = []

    # PRICE FILE RULES
    if file_type == "PRICE":
        price_cols = df.select_dtypes("number").columns
        if len(price_cols) == 0:
            issues.append("NO_NUMERIC_PRICE")

        if len(price_cols) > 0:
            returns = df[price_cols[0]].pct_change()
            if returns.abs().max() > EXTREME_RETURN_LIMIT:
                issues.append("EXTREME_RETURN_DETECTED")

    status = "FAIL" if issues else "PASS"

    return {
        "dataset": path.name,
        "rows": len(df),
        "issues": ";".join(issues) if issues else "OK",
        "status": status,
    }


def main():
    results = []

    for file in DATA_DIR.glob("*.csv"):
        results.append(inspect_file(file))

    report = pd.DataFrame(results)
    print("Live data health check complete.")
    print(report)

    if (report["status"] == "FAIL").any():
        raise RuntimeError("❌ DATA HEALTH CHECK FAILED — PIPELINE HALTED")


if __name__ == "__main__":
    main()
