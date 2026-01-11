from fastapi import FastAPI
from fastapi.responses import JSONResponse
import traceback

from build_mobile_summary import main

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok", "message": "WorldMarketReviewer API is running"}

@app.get("/api/summary")
def get_summary():
    try:
        result = main()
        return result
    except Exception as e:
        # This ensures we actually see the real error in Render logs
        print("🔥 ERROR in /api/summary")
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "error": "summary_failed",
                "details": str(e)
            }
        )
