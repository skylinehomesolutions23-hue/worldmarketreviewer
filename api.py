from fastapi import FastAPI
from build_mobile_summary import main
import uvicorn

app = FastAPI()

@app.get("/api/summary")
def get_summary():
    return main()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
