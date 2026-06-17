import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from database import init_db, get_db_session
from models import (
    NotificationRequest,
    NotificationResponse,
    NotificationHistoryItem,
    SettingsUpdate,
    SettingsResponse,
    StatusResponse,
    NotificationType,
    NotificationStatus,
    ChannelType,
    NotificationRecord,
    NotificationSettings,
)
from redis_queue import enqueue_notification, get_task_status, redis_client
from send_notification import NotificationRouter

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("notification_module.main")


# ---------------------------------------------------------------------------
# Lifespan manager: runs once on startup and shutdown
# ---------------------------------------------------------------------------

# Startup: initialize PostgreSQL/SQLite schema and verify Redis connection.
# Shutdown: close Redis connection pool.
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Notification Module...")
    await init_db()
    try:
        await redis_client.ping()
        logger.info("Redis connection verified.")
    except Exception as exc:
        logger.error("Redis connection failed: %s", exc)
    yield
    logger.info("Shutting down Notification Module...")
    await redis_client.aclose()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Notification Module — ANO VO Humanitarian University",
    description=(
        "Automated notification microservice for the programming assignment "
        "assessment system. Handles email and VK delivery with async queuing, "
        "retry logic, and full audit history."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
# === POST /notifications/send ===
@app.post(
    "/notifications/send",
    response_model=NotificationResponse,
    summary="Enqueue a notification for delivery",
    tags=["Notifications"],
)

# Accept a notification request, persist it as PENDING, and enqueue it for asynchronous processing.
# Returns immediately with a task_id.
# The worker (redis_queue.py worker loop) picks up the task and calls send_notification.py to route it to the correct channel(s).
async def send_notification(payload: NotificationRequest) -> NotificationResponse:
    task_id = str(uuid.uuid4())
    logger.info(
        "Received send request | task_id=%s | type=%s | recipient=%s",
        task_id,
        payload.notification_type,
        payload.recipient_id,
    )

    async with get_db_session() as session:
        record = NotificationRecord(
            task_id=task_id,
            notification_type=payload.notification_type,
            recipient_id=payload.recipient_id,
            channel=payload.channel,
            status=NotificationStatus.PENDING,
            payload=payload.model_dump(mode="json"),
            created_at=datetime.utcnow(),
        )
        session.add(record)
        await session.commit()

    await enqueue_notification(task_id=task_id, payload=payload.model_dump(mode="json"))
    logger.info("Notification enqueued | task_id=%s", task_id)

    return NotificationResponse(
        task_id=task_id,
        status=NotificationStatus.PENDING,
        message="Notification accepted and queued for delivery.",
    )


# === GET /notifications/status/{task_id} ===
@app.get(
    "/notifications/status/{task_id}",
    response_model=StatusResponse,
    summary="Check delivery status of a notification",
    tags=["Notifications"],
)

# Return the current delivery status for a given task_id.
# Status values: PENDING, PROCESSING, SENT, FAILED.
async def get_status(task_id: str) -> StatusResponse:
    async with get_db_session() as session:
        record = await session.get(NotificationRecord, task_id)
        if not record:
            raise HTTPException(status_code=404, detail="Task not found.")

    return StatusResponse(
        task_id=task_id,
        status=record.status,
        channel=record.channel,
        created_at=record.created_at,
        sent_at=record.sent_at,
        error_message=record.error_message,
        attempt_count=record.attempt_count,
    )


# === GET /notifications/history ===
@app.get(
    "/notifications/history",
    response_model=list[NotificationHistoryItem],
    summary="Retrieve notification history with optional filters",
    tags=["Notifications"],
)

# Retrieve notification history. Supports filtering by recipient, type, and delivery status.
# Paginated with limit/offset.
async def get_history(
    recipient_id: Optional[str] = Query(None, description="Filter by recipient ID"),
    notification_type: Optional[NotificationType] = Query(None, description="Filter by type"),
    status: Optional[NotificationStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> list[NotificationHistoryItem]:
    from sqlalchemy import select

    async with get_db_session() as session:
        stmt = select(NotificationRecord)
        if recipient_id:
            stmt = stmt.where(NotificationRecord.recipient_id == recipient_id)
        if notification_type:
            stmt = stmt.where(NotificationRecord.notification_type == notification_type)
        if status:
            stmt = stmt.where(NotificationRecord.status == status)
        stmt = stmt.order_by(NotificationRecord.created_at.desc()).limit(limit).offset(offset)

        result = await session.execute(stmt)
        records = result.scalars().all()

    return [
        NotificationHistoryItem(
            task_id=r.task_id,
            notification_type=r.notification_type,
            recipient_id=r.recipient_id,
            channel=r.channel,
            status=r.status,
            created_at=r.created_at,
            sent_at=r.sent_at,
            attempt_count=r.attempt_count,
        )
        for r in records
    ]


# === GET /notifications/settings/{recipient_id} ===
@app.get(
    "/notifications/settings/{recipient_id}",
    response_model=SettingsResponse,
    summary="Retrieve notification preferences for a user",
    tags=["Settings"],
)

# Return the channel preferences stored for a given user.
# If no settings exist, returns defaults (both channels enabled).
async def get_settings(recipient_id: str) -> SettingsResponse:
    from sqlalchemy import select

    async with get_db_session() as session:
        stmt = select(NotificationSettings).where(
            NotificationSettings.recipient_id == recipient_id
        )
        result = await session.execute(stmt)
        settings = result.scalar_one_or_none()

    if not settings:
        return SettingsResponse(
            recipient_id=recipient_id,
            email_enabled=True,
            vk_enabled=True,
            email_address=None,
            vk_user_id=None,
        )

    return SettingsResponse(
        recipient_id=recipient_id,
        email_enabled=settings.email_enabled,
        vk_enabled=settings.vk_enabled,
        email_address=settings.email_address,
        vk_user_id=settings.vk_user_id,
    )

# === PUT /notifications/settings/{recipient_id} ===
@app.put(
    "/notifications/settings/{recipient_id}",
    response_model=SettingsResponse,
    summary="Update notification preferences for a user",
    tags=["Settings"],
)

#Create or update channel preferences for a user. Allows enabling/disabling email and VK independently and updating contact details.
async def update_settings(recipient_id: str, payload: SettingsUpdate) -> SettingsResponse:
    from sqlalchemy import select

    async with get_db_session() as session:
        stmt = select(NotificationSettings).where(
            NotificationSettings.recipient_id == recipient_id
        )
        result = await session.execute(stmt)
        settings = result.scalar_one_or_none()

        if not settings:
            settings = NotificationSettings(recipient_id=recipient_id)
            session.add(settings)

        if payload.email_enabled is not None:
            settings.email_enabled = payload.email_enabled
        if payload.vk_enabled is not None:
            settings.vk_enabled = payload.vk_enabled
        if payload.email_address is not None:
            settings.email_address = payload.email_address
        if payload.vk_user_id is not None:
            settings.vk_user_id = payload.vk_user_id

        await session.commit()
        await session.refresh(settings)

    logger.info("Settings updated for recipient_id=%s", recipient_id)
    return SettingsResponse(
        recipient_id=recipient_id,
        email_enabled=settings.email_enabled,
        vk_enabled=settings.vk_enabled,
        email_address=settings.email_address,
        vk_user_id=settings.vk_user_id,
    )


# === GET /health ===
@app.get("/health", summary="Health check", tags=["System"])

# Lightweight liveness probe.
# Checks Redis reachability.
# Returns 200 if the service is operational.
async def health_check():
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return JSONResponse(
        content={
            "status": "ok" if redis_ok else "degraded",
            "redis": "connected" if redis_ok else "unreachable",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
