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

   database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bearinmind"

    @property
    def async_database_url(self) -> str:
        # Nếu Railway trả về postgresql://, ta đổi nó thành postgresql+asyncpg://
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def database_url_sync(self) -> str:
        # Logic cũ của bạn cho Alembic (dùng psycopg)
        u = self.async_database_url
        if u.startswith("postgresql+asyncpg"):
            return u.replace("postgresql+asyncpg", "postgresql+psycopg", 1)
        return u

    redis_url: str = "redis://localhost:6379/0"

    chroma_host: str = "localhost"
    chroma_port: int = 3333

    # Auth (JWT)
    jwt_secret_key: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "bearinmind"
    jwt_audience: str = "bearinmind-fe"
    jwt_access_token_expires_minutes: int = 60

    # Generic LLM configuration (works with OpenAI-compatible providers)
    # Examples:
    # - OpenAI: leave `llm_base_url` empty; set `llm_api_key`
    # - OpenRouter: set `llm_base_url="https://openrouter.ai/api/v1"`
    #
    # llm_model_primary   — used for complex tasks: entity extraction, ranking,
    #                        intent classification, answer generation.
    # llm_model_secondary — used for lightweight tasks: conversation title gen,
    #                        short summaries, etc.
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model_primary: str = "google/gemini-2.5-pro"
    llm_model_secondary: str = "google/gemini-3-flash-preview"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
