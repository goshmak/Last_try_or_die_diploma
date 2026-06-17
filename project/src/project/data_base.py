import os
import asyncpg
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Глобальный пул соединений
_pool: Optional[asyncpg.Pool] = None


async def get_db_pool():
    """Получение пула соединений с PostgreSQL (синглтон)"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "notif_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            min_size=1,
            max_size=10,
            command_timeout=60,
        )
        logger.info(f"Database pool created for {os.getenv('DB_HOST', 'localhost')}")
    return _pool


async def get_db_connection():
    """Получение соединения из пула"""
    pool = await get_db_pool()
    return await pool.acquire()


async def close_db_pool():
    """Закрытие пула соединений"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


async def init_database():
    """Создание необходимых таблиц (только для начальной инициализации)"""
    conn = await get_db_connection()
    
    try:
        # Включаем расширение для UUID
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        
        # Таблица уведомлений
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id SERIAL PRIMARY KEY,
                user_id UUID NOT NULL,
                user_type VARCHAR(50) NOT NULL,
                notification_type VARCHAR(50) NOT NULL,
                title VARCHAR(255),
                content TEXT,
                channel VARCHAR(50),
                status VARCHAR(50) DEFAULT 'pending',
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP
            )
        """)
        
        # Таблица настроек пользователей
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_notification_preferences (
                user_id UUID PRIMARY KEY,
                user_type VARCHAR(50) NOT NULL,
                email VARCHAR(255) NOT NULL,
                vk_id VARCHAR(100),
                notification_channel VARCHAR(50) DEFAULT 'email',
                new_assignment_enabled BOOLEAN DEFAULT TRUE,
                deadline_student_enabled BOOLEAN DEFAULT TRUE,
                deadline_teacher_enabled BOOLEAN DEFAULT TRUE,
                assignment_checked_enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для оптимизации
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_user_id 
            ON notifications(user_id)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_created_at 
            ON notifications(created_at)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_status 
            ON notifications(status)
        """)
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        await conn.close()