# backend/worker/run.py
from rq import Worker
from worker.queue import redis

if __name__ == "__main__":
    # Listen on both queues using the shared Redis connection
    worker = Worker(["long", "default"], connection=redis)
    worker.work(with_scheduler=True, burst=False)