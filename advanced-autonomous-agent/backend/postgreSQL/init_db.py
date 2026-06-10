
from backend.postgreSQL.engine import engine, Base
from backend.postgreSQL.models import Job, User, AgentState

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
