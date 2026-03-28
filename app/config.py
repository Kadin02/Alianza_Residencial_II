from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "1234"  #  NUEVO
    ALGORITHM: str = "HS256"  # NUEVO
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  #  NUEVO

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        extra="ignore"
    )

settings = Settings()