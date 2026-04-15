from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Schemes that carry a valid, loadable SQLAlchemy dialect+driver.
_VALID_ASYNC_SCHEMES = ("postgresql+asyncpg://",)
_VALID_SYNC_SCHEMES = ("postgresql+psycopg://",)
# Bare postgresql:// is accepted and normalised automatically.
_BARE_PG_SCHEME = "postgresql://"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bearinmind"

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Reject obviously broken DATABASE_URL values early with a clear message."""
        if not v or not v.strip():
            raise ValueError(
                "DATABASE_URL is empty. "
                "Set it to a valid PostgreSQL connection string, e.g. "
                "postgresql+asyncpg://user:password@host:5432/dbname"
            )

        v = v.strip()

        valid_prefixes = (
            "postgresql+asyncpg://",
            "postgresql+psycopg://",
            "postgresql://",   # normalised automatically by async_database_url
            "postgres://",     # common alias, also normalised
        )
        if not any(v.startswith(p) for p in valid_prefixes):
            raise ValueError(
                f"DATABASE_URL has an unrecognised scheme: '{v[:40]}...'. "
                "Expected a PostgreSQL URL starting with one of: "
                + ", ".join(valid_prefixes)
                + ". "
                "This error typically means the DATABASE_URL environment variable "
                "is not set correctly. "
                "Example: postgresql+asyncpg://user:password@host:5432/dbname"
            )

        return v

    @model_validator(mode="after")
    def check_production_database_url(self) -> "Settings":
        """In non-development environments the DATABASE_URL must be explicitly set."""
        if self.app_env != "development":
            default_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/bearinmind"
            if self.database_url == default_url:
                raise ValueError(
                    f"DATABASE_URL is still set to the local development default "
                    f"but APP_ENV='{self.app_env}'. "
                    "Set DATABASE_URL to the production PostgreSQL connection string "
                    "before starting the service."
                )
        return self

    @property
    def async_database_url(self) -> str:
        """Return a DATABASE_URL that uses the asyncpg driver.

        Handles the common cases where Railway (or other platforms) provide a
        bare ``postgresql://`` or ``postgres://`` URL without a driver suffix.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            # Heroku / some platforms use the shorter alias
            url = "postgresql" + url[len("postgres"):]
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Already has an explicit driver (e.g. postgresql+asyncpg:// or
        # postgresql+psycopg://) — return as-is.
        return url

    @property
    def database_url_sync(self) -> str:
        """Return a DATABASE_URL that uses the synchronous psycopg driver.

        Used by Alembic, which runs in a synchronous context.
        """
        u = self.async_database_url
        if not u:
            raise RuntimeError(
                "Cannot derive a synchronous DATABASE_URL because async_database_url "
                "is empty. Check that DATABASE_URL is set correctly."
            )
        if u.startswith("postgresql+asyncpg://"):
            return u.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if u.startswith("postgresql+psycopg://"):
            # Already synchronous — nothing to do.
            return u
        raise RuntimeError(
            f"Cannot convert '{u[:60]}' to a synchronous URL. "
            "Expected a URL starting with 'postgresql+asyncpg://' or "
            "'postgresql+psycopg://'."
        )

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
