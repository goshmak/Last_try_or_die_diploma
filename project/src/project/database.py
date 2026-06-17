import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from models import Base

logger = logging.getLogger("notification_module.database")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# connect_args is only valid for SQLite; for PostgreSQL it is ignored.
_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    connect_args=_connect_args,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """Create all tables defined in models.py if they do not already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialised (engine: %s).", settings.DATABASE_URL.split("://")[0])


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional async database session.
    Rolls back automatically on exception; commits must be explicit.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
