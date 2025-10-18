import os
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.db import engine, SessionLocal
from app.models import Recording, Transcript, Task


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
    allow_origins=frontend_origins,   # keep explicit prod origins
    allow_origin_regex=r"https://.*\.vercel\.app",  # allow previews
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

def get_db():
    if SessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable (DATABASE_URL not configured)"
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/recordings")
def list_recordings(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    rows = (
        db.query(Recording)
        .order_by(Recording.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "createdAt": r.created_at.isoformat(),
            "durationSec": r.duration_sec,
            "status": r.status.value,
        }
        for r in rows
    ]

@app.get("/recordings/{rid}")
def get_recording(rid: str, db: Session = Depends(get_db)):
    r = db.query(Recording).filter(Recording.id == rid).first()
    if not r:
        raise HTTPException(404, "Recording not found")
    tr = db.query(Transcript).filter(Transcript.recording_id == rid).first()
    return {
        "id": r.id,
        "filename": r.filename,
        "createdAt": r.created_at.isoformat(),
        "durationSec": r.duration_sec,
        "status": r.status.value,
        "summary": tr.summary if tr else None,
    }

@app.get("/recordings/{rid}/tasks")
def get_tasks(rid: str, db: Session = Depends(get_db)):
    tasks = db.query(Task).filter(Task.recording_id == rid).all()
    return [
        {
            "id": t.id,
            "recordingId": t.recording_id,
            "title": t.title,
            "assignee": t.assignee,
            "dueDate": t.due_date.isoformat() if t.due_date else None,
            "priority": t.priority.value if t.priority else None,
            "status": t.status.value,
            "confidence": t.confidence,
        }
        for t in tasks
    ]
