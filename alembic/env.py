import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import create_engine, pool, engine_from_config

from alembic import context

import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# 1. Lấy URL và chuyển đổi cho asyncpg
def get_url():
    # 1. Ưu tiên lấy từ biến môi trường của Railway
    url = os.getenv("DATABASE_URL")
    
    if url:
        # Railway cung cấp postgresql://, ta cần đổi sang postgresql+asyncpg://
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url
    
    # 2. Nếu không có biến môi trường (chạy local), lấy từ alembic.ini
    # Nhưng phải đảm bảo file .ini không chứa "driver://"
    url_from_ini = config.get_main_option("sqlalchemy.url")
    if url_from_ini and "driver://" in url_from_ini:
        # Trả về một URL mặc định chạy local để tránh lỗi crash khi build
        return "postgresql+asyncpg://postgres:postgres@localhost:5432/dbname"
        
    return url_from_ini

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_offline() -> None:
    url = settings.database_url_sync
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    """Chạy migration ở chế độ 'online' (bất đồng bộ)"""
    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Alembic yêu cầu một kết nối đồng bộ, nên ta dùng run_sync để bọc nó
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
