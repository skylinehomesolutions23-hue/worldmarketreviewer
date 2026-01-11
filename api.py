
from fastapi import FastAPI
from build_mobile_summary import main

app = FastAPI()

@app.get("/api/summary")
def get_summary():
    return main()
