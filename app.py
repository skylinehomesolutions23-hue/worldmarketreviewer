# app.py
import os
import uvicorn

PORT = int(os.getenv("PORT", "8000"))

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=PORT, log_level="info")
