import sys
from logging.config import fileConfig
from pathlib import Path

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

def run_migrations_online() -> None:
    # 2. LẤY URL TỪ RAILWAY (Biến DATABASE_URL)
    target_url = os.getenv("DATABASE_URL")
    
    if target_url:
        # Nếu Railway trả về postgresql://, đổi thành postgresql+asyncpg:// để dùng async
        if target_url.startswith("postgresql://"):
            target_url = target_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        # Nếu không có biến môi trường (chạy local), lấy từ file ini
        target_url = config.get_main_option("sqlalchemy.url")

    # 3. Ghi đè cấu hình URL
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = target_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
