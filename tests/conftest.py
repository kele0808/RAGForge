from __future__ import annotations

import os
from pathlib import Path
_TEST_DB_URL = "postgresql+asyncpg://rag:rag@localhost:5432/ragforge_test"
os.environ["DATABASE_URL"] = _TEST_DB_URL
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

REPO_ROOT = Path(__file__).resolve().parent.parent

@pytest.fixture(scope="session")
def _migrated_test_db():
    """
    Session 级fixture， 整个pytest跑一次前吧测试库推到最新schema
    :return:
    """
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", _TEST_DB_URL.replace("+asyncpg", "+psycopg"))
    command.upgrade(cfg, "head")

@pytest_asyncio.fixture
async def db_session(_migrated_test_db):
    """ 每一个test 一个独立session；测试完 TRUNCATE 保持干净"""
    engine = create_async_engine(_TEST_DB_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as session:
            yield session
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE documents, chunks CASCADE"))
        await engine.dispose()
