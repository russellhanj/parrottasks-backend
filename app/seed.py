# app/seed.py
from datetime import datetime, timedelta
import uuid
from app.db import SessionLocal
from app.models import User, Recording, Transcript, Task, RecordingStatusEnum, TaskStatusEnum, PriorityEnum

def main():
    with SessionLocal() as db:
        # 1. user
        user = db.query(User).filter(User.email == "demo@parrottasks.app").first()
        if not user:
            user = User(email="demo@parrottasks.app", name="Demo User")
            db.add(user)
            db.flush()

        # 2. recording
        rid = str(uuid.uuid4())
        rec = Recording(
            id=rid,
            user_id=user.id,
            filename="team-sync-2025-09-01.mp4",
            status=RecordingStatusEnum.summarized,
            created_at=datetime.utcnow(),
            duration_sec=3600,
        )
        db.add(rec)
        db.flush()

        # 3. transcript
        tr = Transcript(
            recording_id=rec.id,
            text="Speaker 1: hello team...\nSpeaker 2: let's align on tasks…",
            summary="Weekly sync. Agreed on timelines and owners.",
            decisions='["Ship MVP in 2 weeks","Use Wrike for tasks"]',
            questions='["Do we need diarization?"]',
        )
        db.add(tr)

        # 4. tasks
        t1 = Task(
            recording_id=rec.id,
            title="Prepare Wrike OAuth app",
            assignee="russell",
            due_date=datetime.utcnow() + timedelta(days=7),
            priority=PriorityEnum.high,
            status=TaskStatusEnum.todo,
            confidence=0.9,
        )
        t2 = Task(
            recording_id=rec.id,
            title="Hook up Whisper transcription in worker",
            assignee="russell",
            priority=PriorityEnum.med,
            status=TaskStatusEnum.todo,
            confidence=0.8,
        )
        db.add_all([t1, t2])
        db.commit()
        print("✅ Seed completed. Recording ID:", rec.id)

if __name__ == "__main__":
    main()
