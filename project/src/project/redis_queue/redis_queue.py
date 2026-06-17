import logging
import json
import os
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable
from uuid import UUID

import redis.asyncio as redis
import torrelque

logger = logging.getLogger(__name__)

# Настройки Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_QUEUE = os.getenv("REDIS_QUEUE", "notifications_queue")

# Глобальные переменные
_redis_client: Optional[redis.Redis] = None
_torrelque: Optional[torrelque.Torrelque] = None
_consumer_task: Optional[asyncio.Task] = None
_message_handler: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None


async def get_redis_connection() -> redis.Redis:
    """Получение соединения с Redis (синглтон)"""
    global _redis_client
    if _redis_client is None or _redis_client.closed:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        # Проверка подключения
        await _redis_client.ping()
        logger.info(f"Redis connection established to {REDIS_HOST}:{REDIS_PORT}")
    return _redis_client


async def get_queue() -> torrelque.Torrelque:
    """Получение очереди Torrelque (синглтон)"""
    global _torrelque
    if _torrelque is None:
        client = await get_redis_connection()
        _torrelque = torrelque.Torrelque(client, queue=REDIS_QUEUE)
        # Запуск периодической очистки для повторной постановки просроченных задач
        _torrelque.schedule_sweep()
        logger.info(f"Torrelque queue '{REDIS_QUEUE}' initialized")
    return _torrelque


async def publish_notification(
    user_id: UUID,
    user_type: str,
    notification_type: str,
    content_data: Dict[str, Any],
    metadata: Optional[Dict] = None,
) -> bool:
    """
    Публикация уведомления в Redis очередь.
    Использует Torrelque для надежной доставки с возможностью повторных попыток.
    """
    max_retries = 3
    retry_delay = 1

    message_data = {
        "user_id": str(user_id),
        "user_type": user_type,
        "notification_type": notification_type,
        "content_data": content_data,
        "metadata": metadata or {},
    }

    for attempt in range(max_retries):
        try:
            queue = await get_queue()
            task_id = await queue.enqueue(message_data)
            logger.info(
                f"Notification published to Redis queue for user {user_id} "
                f"(task_id: {task_id}, attempt: {attempt + 1})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to publish notification (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2**attempt))
            else:
                return False

    return False


async def consume_notifications(handler: Callable[[Dict[str, Any]], Awaitable[None]]):
    """
    Потребление уведомлений из Redis очереди.
    
    Args:
        handler: Асинхронная функция-обработчик сообщений.
                 Принимает один аргумент - словарь с данными сообщения.
    """
    global _message_handler
    _message_handler = handler
    
    queue = await get_queue()
    logger.info(f"Redis consumer started on queue '{REDIS_QUEUE}'")

    while True:
        try:
            # Ожидание нового сообщения (блокирующая операция с таймаутом)
            result = await queue.dequeue(timeout=5)
            
            if result is None:
                # Таймаут - просто продолжаем
                continue
            
            task_id, task_data = result
            
            logger.info(f"Processing task {task_id}: {task_data.get('notification_type')}")

            try:
                # Вызов пользовательского обработчика
                await handler(task_data)
                
                # Успешная обработка - удаляем задачу
                await queue.release(task_id)
                logger.info(f"Task {task_id} completed and released")
                
            except Exception as e:
                logger.error(f"Error processing task {task_id}: {e}")
                # Повторная постановка с задержкой (exponential backoff)
                retry_count = task_data.get("_retry_count", 0)
                if retry_count < 3:
                    task_data["_retry_count"] = retry_count + 1
                    delay = 2**retry_count  # 1, 2, 4 секунды
                    await queue.requeue(task_id, delay=delay)
                    logger.info(f"Task {task_id} requeued with delay {delay}s (retry {retry_count + 1}/3)")
                else:
                    logger.error(f"Task {task_id} failed after 3 retries, moving to dead letter")
                    # Можно сохранить в отдельную очередь или лог
                    await queue.release(task_id)

        except Exception as e:
            logger.error(f"Consumer error: {e}")
            await asyncio.sleep(1)


async def start_redis_consumer(handler: Callable[[Dict[str, Any]], Awaitable[None]]):
    """Запуск Redis consumer как фоновой задачи"""
    global _consumer_task
    if _consumer_task is None or _consumer_task.done():
        _consumer_task = asyncio.create_task(consume_notifications(handler))
        logger.info("Redis consumer task started")
    return _consumer_task


async def stop_redis_consumer():
    """Остановка Redis consumer"""
    global _consumer_task
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            logger.info("Redis consumer task cancelled")
        _consumer_task = None


async def close_redis_connection():
    """Закрытие соединения с Redis"""
    global _redis_client, _torrelque
    if _torrelque:
        # Torrelque не имеет специального метода закрытия
        _torrelque = None
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


async def get_queue_status() -> Dict[str, Any]:
    """Получение статуса очереди"""
    try:
        client = await get_redis_connection()
        queue = await get_queue()
        # Получение количества задач (приблизительное)
        # Redis не предоставляет точное количество, но можно оценить через LLEN
        length = await client.llen(f"torrelque:{REDIS_QUEUE}:queue")
        return {
            "status": "active",
            "queue_name": REDIS_QUEUE,
            "type": "redis",
            "host": REDIS_HOST,
            "queue_length": length,
            "service": "notification_service",
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return {"status": "unknown", "error": str(e)}