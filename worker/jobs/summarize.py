import datetime as dt
from app.db import SessionLocal
from app.models import Recording, Transcript, RecordingStatusEnum

def summarize_recording(recording_id: str):
    db = SessionLocal()
    try:
        rec = db.get(Recording, recording_id)
        if not rec:
            raise ValueError(f"Recording {recording_id} not found")

        # Write a placeholder summary if empty
        tx = db.query(Transcript).filter(Transcript.recording_id == recording_id).one_or_none()
        if tx and (not tx.summary or not tx.summary.strip()):
            tx.summary = "Summary pending (MVP stub)."
            db.commit()

        rec.summarized_at = dt.datetime.utcnow()
        rec.tasks_extracted_at = dt.datetime.utcnow()
        rec.status = RecordingStatusEnum.ready
        db.commit()
        return {"ok": True}
    except Exception as e:
        try:
            rec = db.get(Recording, recording_id)
            if rec:
                rec.status = RecordingStatusEnum.failed
                if hasattr(rec, "error_log"):
                    rec.error_log = (str(e) or "")[:4000]
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()
