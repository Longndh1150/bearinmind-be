from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    debug: bool = True

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/bearinmind"
    )

    @property
    def database_url_sync(self) -> str:
        u = self.database_url
        if u.startswith("postgresql+asyncpg"):
            return u.replace("postgresql+asyncpg", "postgresql+psycopg", 1)
        return u

    redis_url: str = "redis://localhost:6379/0"

    chroma_host: str = "localhost"
    chroma_port: int = 3333


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
