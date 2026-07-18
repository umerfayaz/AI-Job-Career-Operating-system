
from backend.postgreSQL.engine import engine, Base
import backend.postgreSQL.models
import backend.subscription.models

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
