# app/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
import enum
import uuid
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# ===== Enums =====
class PriorityEnum(str, enum.Enum):
    low = "low"
    med = "med"
    high = "high"


class TaskStatusEnum(str, enum.Enum):
    todo = "todo"
    doing = "doing"
    done = "done"


class RecordingStatusEnum(str, enum.Enum):
    # new pipeline states
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"
    # legacy states (seen in prod)
    uploaded = "uploaded"
    transcribed = "transcribed"
    summarized = "summarized"
    error = "error"


# ===== Models =====
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    recordings: Mapped[List["Recording"]] = relationship(back_populates="owner")


def _uuid() -> str:
    return str(uuid.uuid4())


class Recording(Base):
    __tablename__ = "recordings"

    # Use server-side UUID by default (frontend can still supply one if desired)
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Upload metadata (added for Week-2 upload flow)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    r2_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)

    # Processing/status
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[RecordingStatusEnum] = mapped_column(
        PGEnum(RecordingStatusEnum, name="recordingstatusenum", create_type=False),
        server_default="queued",   # server-side default; matches the enum label
        nullable=False,
        index=True,
    )

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="recordings")
    transcript: Mapped[Optional["Transcript"]] = relationship(
        back_populates="recording", uselist=False, cascade="all, delete-orphan"
    )
    tasks: Mapped[List["Task"]] = relationship(
        back_populates="recording", cascade="all, delete-orphan"
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recording_id: Mapped[str] = mapped_column(ForeignKey("recordings.id"), unique=True, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    decisions: Mapped[Optional[str]] = mapped_column(Text)   # JSON stringified list for now
    questions: Mapped[Optional[str]] = mapped_column(Text)   # JSON stringified list
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    recording: Mapped["Recording"] = relationship(back_populates="transcript")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recording_id: Mapped[str] = mapped_column(ForeignKey("recordings.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    assignee: Mapped[Optional[str]] = mapped_column(String(255))
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    priority: Mapped[Optional[PriorityEnum]] = mapped_column(Enum(PriorityEnum))
    status: Mapped[TaskStatusEnum] = mapped_column(Enum(TaskStatusEnum), default=TaskStatusEnum.todo, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    recording: Mapped["Recording"] = relationship(back_populates="tasks")
