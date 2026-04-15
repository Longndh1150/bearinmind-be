#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# 0. Validate DATABASE_URL before doing anything else.
#    A missing or malformed URL causes a cryptic SQLAlchemy error deep inside
#    Alembic; catching it here gives a clear, actionable message instead.
# ---------------------------------------------------------------------------
echo "Validating DATABASE_URL..."

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set." >&2
  echo "       Set it to a valid PostgreSQL connection string, e.g.:" >&2
  echo "       postgresql+asyncpg://user:password@host:5432/dbname" >&2
  exit 1
fi

# Accept the schemes that the app normalises automatically.
case "$DATABASE_URL" in
  postgresql+asyncpg://* | postgresql+psycopg://* | postgresql://* | postgres://*)
    echo "DATABASE_URL scheme looks valid."
    ;;
  *)
    echo "ERROR: DATABASE_URL has an unrecognised scheme." >&2
    echo "       Got: ${DATABASE_URL:0:40}..." >&2
    echo "       Expected one of: postgresql+asyncpg://, postgresql+psycopg://," >&2
    echo "                        postgresql://, postgres://" >&2
    exit 1
    ;;
esac

# Let Pydantic settings perform the full validation (scheme + production check).
python - <<'PYEOF'
import sys
try:
    from app.core.config import Settings
    Settings()
    print("Settings validation passed.")
except Exception as exc:
    print(f"ERROR: Configuration validation failed:\n  {exc}", file=sys.stderr)
    sys.exit(1)
PYEOF

# ---------------------------------------------------------------------------
# 1. Run Alembic migrations
# ---------------------------------------------------------------------------
echo "Running migrations..."
alembic upgrade head

# ---------------------------------------------------------------------------
# 2. Seed reference data
# ---------------------------------------------------------------------------
echo "Seeding data..."
python -m scripts.seed_units

# ---------------------------------------------------------------------------
# 3. Start the API server
# ---------------------------------------------------------------------------
echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
