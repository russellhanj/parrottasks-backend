# app/seed.py
from datetime import datetime, timedelta
import uuid
from app.db import SessionLocal
from app.models import User, Recording, Transcript, Task, RecordingStatusEnum, TaskStatusEnum, PriorityEnum

def main():
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "demo@parrottasks.app").first()
        if not user:
            user = User(email="demo@parrottasks.app", name="Demo User")
            db.add(user); db.flush()

        rid = str(uuid.uuid4())
        rec = Recording(
            id=rid,
            user_id=user.id,
            filename="team-sync-local.mp4",
            status=RecordingStatusEnum.summarized,
            created_at=datetime.utcnow(),
            duration_sec=1800,
        )
        db.add(rec); db.flush()

        tr = Transcript(
            recording_id=rec.id,
            text="Transcript body…",
            summary="Weekly sync summary.",
            decisions='["Ship MVP in 2 weeks"]',
            questions='["Do we need diarization?"]',
        )
        db.add(tr)

        db.add_all([
            Task(
                recording_id=rec.id,
                title="Prepare Wrike OAuth app",
                assignee="russell",
                due_date=datetime.utcnow()+timedelta(days=3),
                priority=PriorityEnum.high,
                status=TaskStatusEnum.todo,
                confidence=0.9,
            ),
            Task(
                recording_id=rec.id,
                title="Hook up Whisper in worker",
                assignee="russell",
                priority=PriorityEnum.med,
                status=TaskStatusEnum.todo,
                confidence=0.8,
            ),
        ])
        db.commit()
        print("Seeded recording:", rec.id)

if __name__ == "__main__":
    main()
