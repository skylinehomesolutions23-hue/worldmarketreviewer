from fastapi import FastAPI
from build_mobile_summary import main as build_summary

app = FastAPI()


@app.get("/api/summary")
def get_summary():
    """
    Returns the latest mobile summary.
    """
    try:
        return build_summary()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/health")
def health():
    """
    Simple health check.
    """
    return {"status": "ok"}


@app.get("/")
def root():
    """
    Root route so Render doesn't show Not Found.
    """
    return {"message": "WorldMarketReviewer API running"}
