from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Security: SECRET_KEY must be 32+ bytes. Fails loudly if missing.
    """
    SECRET_KEY: str
    DATABASE_URL: str = "sqlite:///./veritas.db"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Business rules
    MAX_PENDING_PER_USER: int = 3
    GLOBAL_PENDING_CAP: int = 1000
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100
    SQL_ECHO: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Validate SECRET_KEY length (prevents weak keys)
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters."
                "Generate with: openssl rand -hex 32"
            )

        if not self.DATABASE_URL.startswith("sqlite:///"):
            raise ValueError(
                "Phase 1 supports SQLite only."
                "DATABASE_URL must start with sqlite:///"
            )

        if not (5 <= self.ACCESS_TOKEN_EXPIRE_MINUTES <= 120):
            raise ValueError(
                "ACCESS_TOKEN_EXPIRE_MINUTES must be between 5 and 120"
            )

@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton.
    Why cached: Settings loaded once at startup, reused across requests.
    Prevents re-reading .env on every endpoint call.
    """
    return Settings()

