# app/db.py
from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

# Load environment variables early
load_dotenv()

# ---- Declarative Base ----
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ---- Database URL ----
def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. Expected format: "
            "postgresql+psycopg2://user:pass@host:5432/dbname"
        )
    # Enforce psycopg2 driver explicitly
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


# ---- Engine & Session ----
try:
    DATABASE_URL = _database_url()
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # reconnects automatically if idle timeout
        pool_size=5,
        max_overflow=10,
        future=True,
    )
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
except Exception as e:
    # Keep app importable even if DB not configured
    engine = None
    SessionLocal = None
    print(f"[db] ⚠️ Database not configured: {e}")
