from __future__ import annotations
from collections.abc import AsyncIterator
from functools import lru_cache
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from rag.config import settings

@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """
    进程内唯一的异步 engine， lru_cache 保证只创建一次
    :return:
    """
    return create_async_engine(settings.database_url, pool_pre_ping=True)

@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)

async def get_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI 风格 yield 一个 session， 退出时自动关闭
    :return:
    """
    async with get_sessionmaker()() as session:
        yield session

