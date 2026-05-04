"""
config.py — UPDATED

What changed:
  - Added TIMESCALE_URL for the asyncpg connection to TimescaleDB (port 5433).
"""

from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "Mission-Critical IMS"

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://admin:priyanshu123@postgres:5432/ims_db"
    )
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379")

    # TimescaleDB — same creds, different host/port, different DB  (NEW)
    TIMESCALE_URL: str = os.getenv(
        "TIMESCALE_URL",
        "postgresql://admin:priyanshu123@timescaledb:5432/ims_metrics"
    )

    SIGNAL_WINDOW_SECONDS: int = 10
    RATE_LIMIT_PER_SECOND: int = 10000


settings = Settings()