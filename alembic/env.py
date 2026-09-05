from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from rag.config import settings
from rag.models.document import Base  # 触发 Document 注册
from rag.models import chunk  # noqa: F401  触发 Chunk 注册
# Alembic Config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
# 把 asyncpg URL 转成同步 URL 给 Alembic 用
# 如果调用方设置了url，用传过来的，否则settings 读默认值
if not config.get_main_option("sqlalchemy.url"):
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg")
    config.set_main_option("sqlalchemy.url", sync_url)
# 这个是 Alembic autogenerate 比对的目标
target_metadata = Base.metadata
def run_migrations_offline() -> None:
    """生成 SQL 但不真的连数据库（我们暂时用不到，但模板要求存在）"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
def run_migrations_online() -> None:
    """真连数据库跑迁移（`alembic upgrade head` 走这里）"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()