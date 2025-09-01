from fastapi import FastAPI

app = FastAPI(title="ParrotTasks API")

@app.get("/healthz")
def healthz():
    return {"ok": True}