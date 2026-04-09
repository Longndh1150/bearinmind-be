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
    def database_url_sync(self) -> str:
        u = self.database_url
        if u.startswith("postgresql+asyncpg"):
            return u.replace("postgresql+asyncpg", "postgresql+psycopg", 1)
        return u

    redis_url: str = "redis://localhost:6379/0"

    chroma_host: str = "localhost"
    chroma_port: int = 3333

    # Generic LLM configuration (works with OpenAI-compatible providers)
    # Examples:
    # - OpenAI: leave `llm_base_url` empty; set `llm_api_key`, `llm_model="gpt-4o-mini"`
    # - OpenRouter: set `llm_base_url="https://openrouter.ai/api/v1"`,
    #   `llm_model="openai/gpt-4o-mini"` (or any OpenRouter model id)
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
