import asyncio
import json
import logging
import math
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger("notification_module.queue")

# ---------------------------------------------------------------------------
# Redis client (shared singleton)
# ---------------------------------------------------------------------------
redis_client: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)

QUEUE_KEY = settings.REDIS_QUEUE_NAME
RETRY_QUEUE_KEY = f"{QUEUE_KEY}:retry"


# ---------------------------------------------------------------------------
# Producer helpers
# ---------------------------------------------------------------------------

# === Push a notification task onto the Redis queue ===
async def enqueue_notification(task_id: str, payload: dict[str, Any]) -> None:
    envelope = json.dumps({"task_id": task_id, "attempt": 0, "payload": payload})
    await redis_client.rpush(QUEUE_KEY, envelope)
    logger.debug("Enqueued task_id=%s to queue '%s'.", task_id, QUEUE_KEY)

# === Re-enqueue a failed task with incremented attempt counter after a delay ===
# If MAX_RETRY_ATTEMPTS is exceeded, mark the database record as FAILED.
async def _requeue_with_backoff(envelope: dict[str, Any], error: str) -> None:
    from database import get_db_session
    from models import NotificationRecord, NotificationStatus

    attempt = envelope.get("attempt", 0) + 1
    task_id = envelope["task_id"]

    if attempt > settings.MAX_RETRY_ATTEMPTS:
        logger.error(
            "Task exhausted retries | task_id=%s | attempts=%d | error=%s",
            task_id,
            attempt - 1,
            error,
        )
        async with get_db_session() as session:
            record = await session.get(NotificationRecord, task_id)
            if record:
                record.status = NotificationStatus.FAILED
                record.error_message = f"Exhausted {settings.MAX_RETRY_ATTEMPTS} attempts. Last error: {error}"
                record.attempt_count = attempt - 1
                await session.commit()
        return

    # Exponential backoff: delay = base ^ attempt (capped at 300 s)
    delay = min(math.pow(settings.RETRY_BASE_DELAY, attempt), 300.0)
    logger.warning(
        "Scheduling retry | task_id=%s | attempt=%d | delay=%.1fs | error=%s",
        task_id,
        attempt,
        delay,
        error,
    )
    await asyncio.sleep(delay)

    envelope["attempt"] = attempt
    await redis_client.rpush(QUEUE_KEY, json.dumps(envelope))


# ---------------------------------------------------------------------------
# Status helper (used by GET /notifications/status)
# ---------------------------------------------------------------------------

# Check whether a task_id exists in the Redis queue (still pending).
# Returns None if not found in queue (may be processing or completed in DB).
async def get_task_status(task_id: str) -> dict[str, Any] | None:
    # Scan the queue — O(n) but acceptable for a prototype
    items = await redis_client.lrange(QUEUE_KEY, 0, -1)
    for item in items:
        env = json.loads(item)
        if env.get("task_id") == task_id:
            return env
    return None


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

# Deserialise one queue item and delegate to the notification router.
# Updates the database record on success or schedules a retry on failure.
async def _process_envelope(raw: str) -> None:
    from database import get_db_session
    from models import NotificationRecord, NotificationRequest, NotificationStatus
    from send_notification import NotificationRouter

    envelope: dict[str, Any] = json.loads(raw)
    task_id: str = envelope["task_id"]
    attempt: int = envelope.get("attempt", 0)
    payload: dict[str, Any] = envelope["payload"]

    logger.info("Processing task | task_id=%s | attempt=%d", task_id, attempt)

    # Mark record as PROCESSING
    async with get_db_session() as session:
        record = await session.get(NotificationRecord, task_id)
        if record:
            record.status = NotificationStatus.PROCESSING
            record.attempt_count = attempt + 1
            await session.commit()

    try:
        request = NotificationRequest(**payload)
        router = NotificationRouter()
        await router.route(task_id=task_id, request=request)

        # Mark as SENT on success
        async with get_db_session() as session:
            record = await session.get(NotificationRecord, task_id)
            if record:
                record.status = NotificationStatus.SENT
                record.sent_at = datetime.utcnow()
                await session.commit()

        logger.info("Task delivered | task_id=%s", task_id)

    except Exception as exc:
        logger.exception("Task failed | task_id=%s | error=%s", task_id, exc)
        await _requeue_with_backoff(envelope, str(exc))

# Single worker coroutine.
# Blocks on BLPOP with a 5-second timeout so that it wakes up periodically and can be cancelled cleanly on shutdown.
async def _worker_loop(worker_id: int) -> None:
    logger.info("Worker %d started, listening on queue '%s'.", worker_id, QUEUE_KEY)
    while True:
        try:
            # BLPOP returns (key, value) or None on timeout
            result = await redis_client.blpop(QUEUE_KEY, timeout=5)
            if result is None:
                continue  # Timeout — loop and wait again
            _, raw = result
            await _process_envelope(raw)
        except asyncio.CancelledError:
            logger.info("Worker %d shutting down.", worker_id)
            break
        except Exception as exc:
            logger.exception("Worker %d encountered unexpected error: %s", worker_id, exc)
            await asyncio.sleep(1)  # Brief pause before continuing

# === Launch concurrency worker coroutines ===
# Call this from a separate process or via python worker.py.
# The workers run until cancelled (e.g. on SIGINT / SIGTERM).
async def run_worker(concurrency: int | None = None) -> None:
    n = concurrency or settings.WORKER_CONCURRENCY
    logger.info("Starting %d notification workers.", n)
    tasks = [asyncio.create_task(_worker_loop(i)) for i in range(n)]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All workers stopped.")
