import asyncio
import logging
import signal

from config import settings
from database import init_db
from redis_queue import run_worker

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/worker.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("notification_module.worker")


async def main() -> None:
    logger.info("Initialising database...")
    await init_db()
    logger.info("Worker process starting (concurrency=%d).", settings.WORKER_CONCURRENCY)
    await run_worker(concurrency=settings.WORKER_CONCURRENCY)


def _handle_signal(sig, frame):
    logger.info("Signal %s received, shutting down workers.", sig)
    raise SystemExit(0)


if __name__ == "__main__":
    import pathlib
    pathlib.Path("logs").mkdir(exist_ok=True)

    # Graceful shutdown on SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, _handle_signal)
    try:
        signal.signal(signal.SIGTERM, _handle_signal)
    except AttributeError:
        pass  # SIGTERM not available on Windows

    try:
        asyncio.run(main())
    except SystemExit:
        logger.info("Worker stopped.")
