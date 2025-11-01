import datetime as dt
import os
import subprocess
import tempfile
from sqlalchemy import select
from worker.queue import q_default, retry_policy
from app.db import SessionLocal
from app.models import Recording, Transcript
from app.r2 import download_to_temp

from worker.jobs.summarize import summarize_recording  # late import avoidance

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")

def _extract_wav(input_path: str) -> str:
    """
    Convert input media to mono 16kHz WAV for transcription.
    Returns path to the WAV file. Caller must os.remove().
    """
    wav_fd, wav_path = tempfile.mkstemp(prefix="audio_", suffix=".wav")
    os.close(wav_fd)
    # ffmpeg -y -i input -ac 1 -ar 16000 -vn -f wav output.wav
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        "-vn",
        "-f", "wav",
        wav_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return wav_path

def transcribe_recording(recording_id: str):
    db = SessionLocal()
    input_path = None
    wav_path = None
    try:
        rec = db.get(Recording, recording_id)
        if not rec:
            raise ValueError(f"Recording {recording_id} not found")

        if not rec.r2_key:
            raise ValueError("Recording is missing r2_key")

        # mark as processing
        rec.status = "processing"
        if getattr(rec, "upload_completed_at", None) is None:
            rec.upload_completed_at = dt.datetime.utcnow()
        db.commit()

        # 1) Download original media from R2
        input_path = download_to_temp(rec.r2_key)

        # 2) Extract normalized WAV for Whisper
        wav_path = _extract_wav(input_path)

        # 3) (Task 3) Run Whisper here; for now, write placeholder Transcript
        tx = db.execute(
            select(Transcript).where(Transcript.recording_id == recording_id)
        ).scalar_one_or_none()
        if tx is None:
            tx = Transcript(recording_id=recording_id, text="(transcription pending)")
            db.add(tx)
            db.commit()

        # mark "transcribed"
        rec.transcribed_at = dt.datetime.utcnow()
        db.commit()

        # 4) Chain summarization
        q_default.enqueue(summarize_recording, recording_id, retry=retry_policy())
        return {"ok": True}
    except Exception as e:
        try:
            rec = db.get(Recording, recording_id)
            if rec:
                rec.status = "failed"
                if hasattr(rec, "error_log"):
                    rec.error_log = (str(e) or "")[:4000]
                db.commit()
        except Exception:
            pass
        raise
    finally:
        # cleanup temp files
        for p in (wav_path, input_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        db.close()