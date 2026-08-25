"""Alembic 迁移环境配置

核心功能：
  1. 从 .env 文件读取 DATABASE_URL，自动转换为同步驱动供 Alembic 使用
  2. 绑定 ORM Base.metadata 支持 autogenerate
"""

import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# ── 加载 .env 文件 ──
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── 导入 ORM 模型（确保 autogenerate 能检测到所有表） ──
from app.db import Base
from app.models.database import Clip, Task  # noqa: F401

config = context.config

# ── 动态覆盖数据库 URL ──
# 从环境变量读取异步 URL，转换为同步驱动（Alembic 不支持 asyncpg）
database_url = os.getenv("DATABASE_URL", "")
if database_url:
    # asyncpg -> psycopg（同步）
    sync_url = database_url.replace("+asyncpg", "+psycopg")
    config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 使用 ORM Base 的 metadata 支持 autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以 'offline' 模式运行迁移 —— 只生成 SQL 脚本不连接数据库"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以 'online' 模式运行迁移 —— 连接数据库并执行"""
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
