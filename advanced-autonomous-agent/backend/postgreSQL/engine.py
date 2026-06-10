from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = (
    "postgresql+asyncpg://postgres:ashes123@postgres:5432/agentic_ai_saas"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=True
)

AsyncSessionLocal =  async_sessionmaker(
    engine,
    expire_on_commit=True
)

Base = declarative_base()