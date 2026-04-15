#!/bin/bash

# 1. Tự động cập nhật cấu trúc Database mới nhất
echo "Running migrations..."
alembic upgrade head

# 2. Đổ dữ liệu mẫu (Seeding)
# Lưu ý: Nếu dữ liệu đã có rồi, script này nên được viết để không chèn trùng
echo "Seeding data..."
python -m scripts.seed.units

# 3. Khởi chạy API
echo "Starting server..."
# Dùng ${PORT:-8000} nghĩa là: dùng port Railway cấp, nếu không có thì mặc định 8000
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}