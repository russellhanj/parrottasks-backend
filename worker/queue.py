# backend/worker/queue.py
import os
from redis import Redis
from rq import Queue, Retry
from rq.logutils import setup_loghandlers

setup_loghandlers()

REDIS_URL = os.getenv("UPSTASH_REDIS_URL", "redis://localhost:6379/0")

# IMPORTANT: don't pass ssl=...; let rediss:// imply TLS
redis = Redis.from_url(REDIS_URL)

q_long = Queue("long", connection=redis, default_timeout=60 * 20)      # CPU/IO heavy
q_default = Queue("default", connection=redis, default_timeout=60 * 5) # lighter jobs

def retry_policy() -> Retry:
    return Retry(max=3, interval=[60, 300, 1800])
