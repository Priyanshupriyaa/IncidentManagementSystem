from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.incidents import Base
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def init_db():
    """Requirement: The system cannot crash if persistence layer is slow."""
    async with engine.begin() as conn:
        # This creates the work_items table automatically on startup
        await conn.run_sync(Base.metadata.create_all)

# Postgres: Source of Truth (Work Items & RCA) [cite: 18]
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@postgres:5432/ims_db")
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# MongoDB: Data Lake (Raw Signals) [cite: 16]
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")
mongo_client = AsyncIOMotorClient(MONGODB_URL)
mongo_db = mongo_client.ims_logs 

async def get_db():
    async with async_session() as session:
        yield session