# migrations/env.py (top of file)
from logging.config import fileConfig
import os
from dotenv import load_dotenv
load_dotenv()  # <-- loads .env so DATABASE_URL exists

from sqlalchemy import engine_from_config, pool
from alembic import context
from app.db import Base
import app.models  # ensure models imported

config = context.config
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
