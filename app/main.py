# app/main.py
import os
import uuid
import tempfile
from datetime import datetime
from hashlib import sha256

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from app.db import engine, SessionLocal
from app.models import Recording, Transcript, Task, RecordingStatusEnum, User
from app.r2 import upload_fileobj

from worker.queue import q_long, retry_policy, redis
from worker.jobs.transcribe import transcribe_recording

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
    allow_origin_regex=r"https://.*\.vercel\.app",  # allow Vercel previews
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/db/health")
def db_health():
    try:
        if engine is None:
            return {"ok": False, "error": "engine is None (DATABASE_URL not set)"}
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
            detail="Database unavailable (DATABASE_URL not configured)",
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- MIME normalization for tricky browsers (e.g., macOS Voice Memos .m4a) ----
def guess_mime(filename: str, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if ct:
        return ct
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".m4a":
        return "audio/mp4"
    if ext == ".mp3":
        return "audio/mpeg"
    if ext == ".wav":
        return "audio/wav"
    if ext == ".mp4":
        return "video/mp4"
    return "application/octet-stream"


def _ensure_user_exists(db: Session, user_id: int) -> None:
    """Week-2 convenience: ensure a placeholder user exists so uploads don't fail on FK."""
    exists = db.query(User.id).filter(User.id == user_id).first()
    if not exists:
        db.add(User(id=user_id, email=f"user{user_id}@example.com", name="Placeholder"))
        db.commit()


# =========================
#      Upload endpoint
# =========================
@app.post("/recordings")
async def create_recording(
    file: UploadFile = File(...),
    user_id: int = Form(1),  # temporary until auth lands
    db: Session = Depends(get_db),
):
    allowed = {
        "video/mp4",
        "audio/mp4",    # common for .m4a from macOS/iOS
        "audio/x-m4a",
        "audio/m4a",
        "audio/mpeg",   # mp3
        "audio/aac",
        "audio/x-aac",
        "audio/wav",
        "audio/x-wav",
    }

    # Normalize & validate
    mime = guess_mime(file.filename, file.content_type)
    if mime not in allowed:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type: {file.content_type} (normalized: {mime})",
        )

    # Optional max size (bytes). Env override; default 1.5 GB.
    try:
        max_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(1_500_000_000)))
    except ValueError:
        max_bytes = 1_500_000_000

    # Stream to temp file while hashing (O(1) memory)
    hasher = sha256()
    total = 0
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File exceeds max allowed size",
                    )
                hasher.update(chunk)
                tmp.write(chunk)
    finally:
        await file.close()

    sha = hasher.hexdigest()
    key = f"uploads/{datetime.utcnow():%Y/%m/%d}/{uuid.uuid4()}-{file.filename}"

    # Upload to R2 with normalized MIME
    try:
        with open(tmp_path, "rb") as fh:
            upload_fileobj(fh, key, content_type=mime)
    finally:
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass

    _ensure_user_exists(db, user_id)

    # Persist metadata
    rec = Recording(
        user_id=user_id,
        filename=file.filename,
        mime_type=mime,       # use normalized value
        file_size=total,
        sha256=sha,
        r2_key=key,
        status=RecordingStatusEnum.uploaded,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    return {
        "id": rec.id,
        "filename": rec.filename,
        "createdAt": rec.created_at.isoformat(),
        "durationSec": rec.duration_sec,
        "status": rec.status.value,
        "fileSize": rec.file_size,
        "mimeType": rec.mime_type,
        "sha256": rec.sha256,
    }


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

@app.post("/recordings/{recording_id}/process")
def trigger_processing(recording_id: str, db: Session = Depends(get_db)):
    rec = db.query(Recording).filter(Recording.id == recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Normalize legacy statuses to queued so the pipeline can run
    legacy_statuses = {
        RecordingStatusEnum.uploaded,
        RecordingStatusEnum.transcribed,
        RecordingStatusEnum.summarized,
        RecordingStatusEnum.error,
    }
    if rec.status in legacy_statuses:
        rec.status = RecordingStatusEnum.queued
        db.commit()

    # If it’s already processing or ready, don’t enqueue again
    if rec.status in (RecordingStatusEnum.processing, RecordingStatusEnum.ready):
        return {"ok": True, "status": rec.status.value, "jobId": None}

    # Enqueue the transcription job (MVP stub for now)
    job = q_long.enqueue(transcribe_recording, recording_id, retry=retry_policy())
    return {"ok": True, "status": rec.status.value, "jobId": job.get_id()}

@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    recs = db.query(func.count(Recording.id)).scalar() or 0
    tasks = db.query(func.count(Task.id)).scalar() or 0
    return {"recordings": recs, "tasks": tasks}

@app.get("/healthz/worker")
def worker_health():
    try:
        return {"redis": bool(redis.ping())}
    except Exception as e:
        return {"redis": False, "error": str(e)}