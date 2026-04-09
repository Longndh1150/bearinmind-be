from __future__ import annotations

from pathlib import Path


def parse_uv_lock_versions(lock_path: str = "uv.lock") -> dict[str, str]:
    text = Path(lock_path).read_text(encoding="utf-8")
    pkgs: dict[str, str] = {}
    name: str | None = None

    for line in text.splitlines():
        s = line.strip()
        if s == "[[package]]":
            name = None
            continue
        if s.startswith('name = "') and s.endswith('"'):
            name = s[len('name = "') : -1]
            continue
        if name and name not in pkgs and s.startswith('version = "') and s.endswith('"'):
            pkgs[name] = s[len('version = "') : -1]
            continue

    return pkgs


if __name__ == "__main__":
    pkgs = parse_uv_lock_versions()
    direct = [
        "fastapi",
        "uvicorn",
        "pydantic-settings",
        "sqlalchemy",
        "asyncpg",
        "alembic",
        "psycopg",
        "httpx",
        "langchain-core",
        "langgraph",
        "langchain-openai",
        "chromadb",
        "redis",
        "ruff",
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
    ]
    for d in direct:
        print(f"{d}={pkgs.get(d)}")
