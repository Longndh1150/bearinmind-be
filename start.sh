#!/bin/bash

# Đợi Postgres sẵn sàng (Railway cung cấp biến DATABASE_URL)
# Bước này cực kỳ quan trọng để migration không bị crash do DB chưa khởi động xong
echo "Checking database connection..."

# 1. Chạy Migrations
echo "Running migrations..."
alembic upgrade head

# 2. Chạy Seeding
echo "Seeding data..."
python -m scripts.seed_units

# 3. Chạy API chính
echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
