"""PostgreSQL-backed LangGraph checkpointer lifecycle.

Uses AsyncPostgresSaver with psycopg3 connection pool.
Auto-creates checkpoint tables on startup via setup().
"""

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


async def init_checkpointer(conn_string: str) -> None:
    """Create connection pool + AsyncPostgresSaver, then auto-create tables.

    Pool connections use autocommit=True (required by setup() for
    CREATE INDEX CONCURRENTLY which cannot run inside a transaction).
    """
    global _pool, _checkpointer

    _pool = AsyncConnectionPool(
        conninfo=conn_string,
        max_size=20,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    await _pool.open()

    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()

    logger.warning("[CHECKPOINT] PostgresSaver initialized — tables ready")


async def close_checkpointer() -> None:
    """Close the connection pool on shutdown."""
    global _pool, _checkpointer

    if _pool:
        await _pool.close()
        logger.warning("[CHECKPOINT] Connection pool closed")

    _pool = None
    _checkpointer = None


def get_checkpointer() -> AsyncPostgresSaver:
    """Return the shared checkpointer instance. Raises if not initialized."""
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized — call init_checkpointer() first")
    return _checkpointer
