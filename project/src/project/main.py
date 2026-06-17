import asyncio
import os
import logging
from uuid import UUID

from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
from redis_queue.redis_queue import (
    publish_notification,
    start_redis_consumer,
    stop_redis_consumer,
    close_redis_connection,
    get_queue_status,
)

# from files
from background_processes import check_upcoming_deadlines
from data_base import get_db_connection, init_database
from models import NotificationType, UserPreference
from logger import setup_global_logger
from sends.send_vk_notification import close_vk_bot
from sends.send_notification import send_notification


setup_global_logger(log_file_path="main_project.log")

logger = logging.getLogger(__name__)
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запуск БД
    init_database()
    
    # Запуск фоновой задачи проверки дедлайнов
    deadline_task = asyncio.create_task(check_upcoming_deadlines())
    
    # Запуск Redis consumer
    consumer_task = await start_redis_consumer(send_notification_wrapper)

    logger.info("Notification service started with Redis queue")
    logger.info("Service will receive requests via HTTP and process via Redis")

    yield
    
    # Код завершения (Shutdown)
    logger.info("Shutting down notification service...")
    
    deadline_task.cancel()
    try:
        await deadline_task
    except asyncio.CancelledError:
        logger.info("Deadline checker task cancelled")
    
    # Остановка consumer и закрытие соединения
    await stop_redis_consumer()
    await close_redis_connection()
    await close_vk_bot()
    logger.info("Notification service shut down")


# Передаем lifespan в параметр приложения
app = FastAPI(title="Notification Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def send_notification_wrapper(message_data: Dict[str, Any]):
    """Адаптер для вызова send_notification из сообщения"""
    from sends.send_notification import send_notification
    from models import NotificationType
    from uuid import UUID
    
    await send_notification(
        user_id=UUID(message_data["user_id"]),
        user_type=message_data["user_type"],
        notification_type=NotificationType(message_data["notification_type"]),
        content_data=message_data["content_data"],
        metadata=message_data.get("metadata"),
    )

# API эндпоинты
@app.post("/api/notifications/send")
async def send_notification_endpoint(
    user_id: UUID,
    user_type: str,
    notification_type: NotificationType,
    content_data: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """
    API для отправки уведомления.
    Сообщение отправляется в Redis очередь для асинхронной обработки.
    """
    try:
        # Отправляем в очередь Redis
        success = await publish_notification(
            user_id=user_id,
            user_type=user_type,
            notification_type=notification_type.value,
            content_data=content_data,
            metadata={"source": "api_gateway", "timestamp": None}
        )
        
        if not success:
            raise HTTPException(status_code=503, detail="Notification service unavailable")
            
        return {
            "message": "Notification queued for sending",
            "status": "queued",
            "user_id": str(user_id),
            "notification_type": notification_type.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notifications/send/batch")
async def send_batch_notifications_endpoint(
    notifications: List[Dict[str, Any]]
):
    """
    Массовая отправка уведомлений через очередь.
    """
    results = []
    
    for notif in notifications:
        try:
            success = await publish_notification(
                user_id=UUID(notif["user_id"]),
                user_type=notif["user_type"],
                notification_type=notif["notification_type"],
                content_data=notif["content_data"],
                metadata=notif.get("metadata")
            )
            
            results.append({
                "user_id": notif["user_id"],
                "status": "queued" if success else "failed"
            })
            
        except Exception as e:
            logger.error(f"Error queuing batch notification: {e}")
            results.append({
                "user_id": notif["user_id"],
                "status": "error",
                "error": str(e)
            })
    
    return {
        "message": f"Processed {len(notifications)} notifications",
        "results": results
    }


@app.get("/api/notifications/queue/status")
async def get_queue_status_endpoint():
    """Проверка статуса очереди"""
    return await get_queue_status()


@app.post("/api/notifications/preferences")
async def update_notification_preferences(preferences: UserPreference):
    """Обновление настроек уведомлений пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO user_notification_preferences 
            (user_id, user_type, email, vk_id, notification_channel,
             new_assignment_enabled, deadline_student_enabled, 
             deadline_teacher_enabled, assignment_checked_enabled,
             updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                user_type = EXCLUDED.user_type,
                email = EXCLUDED.email,
                vk_id = EXCLUDED.vk_id,
                notification_channel = EXCLUDED.notification_channel,
                new_assignment_enabled = EXCLUDED.new_assignment_enabled,
                deadline_student_enabled = EXCLUDED.deadline_student_enabled,
                deadline_teacher_enabled = EXCLUDED.deadline_teacher_enabled,
                assignment_checked_enabled = EXCLUDED.assignment_checked_enabled,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                str(preferences.user_id),
                preferences.user_type,
                preferences.email,
                preferences.vk_id,
                preferences.notification_channel.value,
                preferences.notifications_enabled.get("new_assignment", True),
                preferences.notifications_enabled.get("deadline_student", True),
                preferences.notifications_enabled.get("deadline_teacher", True),
                preferences.notifications_enabled.get("assignment_checked", True),
            ),
        )

        conn.commit()
        return {"message": "Preferences updated successfully"}
    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@app.get("/api/notifications/history/{user_id}")
async def get_notification_history(user_id: UUID, limit: int = 50):
    """Получение истории уведомлений пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT notification_id, user_id, user_type, notification_type, 
                   title, content, channel, status, created_at, sent_at
            FROM notifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
            """,
            (str(user_id), limit),
        )

        notifications = cursor.fetchall()
        
        # Преобразуем UUID для JSON сериализации
        for notif in notifications:
            notif["user_id"] = str(notif["user_id"])
        
        return {"notifications": notifications, "total": len(notifications)}
    except Exception as e:
        logger.error(f"Error getting notification history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@app.get("/api/notifications/stats")
async def get_notification_stats():
    """Статистика по уведомлениям"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                notification_type,
                channel,
                status,
                COUNT(*) as count,
                DATE(created_at) as date
            FROM notifications
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY notification_type, channel, status, DATE(created_at)
            ORDER BY date DESC
        """)

        stats = cursor.fetchall()
        return {"stats": stats, "period": "last_30_days"}
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    # Проверка подключения к БД
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"
    
    # Проверка Redis
    redis_status = "unknown"
    try:
        from redis_queue.redis_queue import get_redis_connection
        redis_client = await get_redis_connection()
        await redis_client.ping()
        redis_status = "connected"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = "disconnected"
    
    return {
        "status": "healthy" if db_status == "connected" and redis_status == "connected" else "degraded",
        "service": "notification_service",
        "database": db_status,
        "redis": redis_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)