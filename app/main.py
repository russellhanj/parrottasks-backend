import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from dotenv import load_dotenv

from app.db import engine  # ⬅️ add this import

load_dotenv()

app = FastAPI(title="ParrotTasks API")

frontend_origins = [
    os.getenv("FRONTEND_ORIGIN", ""),
    "http://localhost:3000",
    "https://localhost:3000",
]
frontend_origins = [o for o in frontend_origins if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True}

# ⬇️ new endpoint
@app.get("/db/health")
def db_health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/db/ping")
def db_ping():
    if engine is None:
        return {"ok": False, "error": "engine is None (DATABASE_URL not set)"}
    with engine.begin() as conn:
        row = conn.execute(text("SELECT now() AS ts")).mappings().first()
    return {"ok": True, "ts": row["ts"].isoformat()}