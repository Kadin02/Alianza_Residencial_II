from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"  # NUEVO
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  #  NUEVO
    DEFAULT_ADMIN_USER: str = "admin"
    DEFAULT_ADMIN_PASS: str
    ALLOWED_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        extra="ignore"
    )

settings = Settings()