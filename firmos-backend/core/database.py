"""Database connection management using asyncpg pool."""

import asyncpg
from typing import Optional

from core.config import settings
from core.logging import log


class Database:
    """Singleton wrapper around asyncpg pool."""
    pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def connect(cls):
        """Initialize the connection pool."""
        if cls.pool is None:
            try:
                cls.pool = await asyncpg.create_pool(
                    settings.database_url,
                    min_size=2,
                    max_size=10,
                )
                log.info("database_pool_initialized")
            except Exception as exc:
                log.error("database_connection_failed", error=str(exc))
                if settings.strict_no_mock:
                    raise
                # ponytail: local UI work can start without a database; production cannot.
                cls.pool = None

    @classmethod
    async def close(cls):
        """Close the connection pool."""
        if cls.pool:
            await cls.pool.close()
            log.info("database_pool_closed")


async def get_db_pool() -> Optional[asyncpg.Pool]:
    """Dependency to get the raw asyncpg pool."""
    return Database.pool
