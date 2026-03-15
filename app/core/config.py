from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Laundry Management System"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "SUPER_SECRET_KEY_CHANGE_ME" # Change in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Neon Cloud PostgreSQL URL
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@host/dbname"

    class Config:
        env_file = ".env"

settings = Settings()