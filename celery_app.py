"""Celery instance (broker + result backend = Redis).

Set REDIS_URL to change the broker/backend (default: redis://localhost:6379/0).
Set CELERY_TASK_ALWAYS_EAGER=1 to run tasks synchronously in-process
(handy for local dev without Redis).
"""
from __future__ import annotations

import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() in ("1", "true", "yes")

# In eager mode tasks run in-process; avoid the Redis backend so local dev
# doesn't require a running Redis just to read task state.
broker = "memory://" if EAGER else REDIS_URL
backend = "cache+memory://" if EAGER else REDIS_URL

celery_app = Celery("mathpix", broker=broker, backend=backend, include=["tasks"])
celery_app.conf.update(
    task_track_started=True,
    task_always_eager=EAGER,
    task_eager_propagates=EAGER,
    result_expires=3600,
)
