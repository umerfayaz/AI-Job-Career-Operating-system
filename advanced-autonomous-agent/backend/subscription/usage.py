from datetime import datetime, UTC
from fastapi import HTTPException
from backend.redis.redis_memory import redis_client

class UsageService:

    @staticmethod
    async def check_daily_workflow_limit( *,
        user_id: str, 
        daily_limit: int,
        workflow_type: str = "frontend"
    ) -> dict:

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        key = f"usage:{workflow_type}:{user_id}:{today}"

        current = await redis_client.get(key)
        current = int(current) if current else 0

        if daily_limit != -1 and current >= daily_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "workflow_limit_reached",
                    "workflow_type": workflow_type,
                    "used": current,
                    "remaining": 0
                }
            )
        
        await redis_client.incr(key)
        await redis_client.expire(key, 86400)

        return {
            "limit": daily_limit,
            "used": current + 1,
            "remaining": -1 if daily_limit == -1 else daily_limit - current - 1
        }
    
    @staticmethod
    async def get_usage(
        *,
        user_id: str,
        workflow_type: str = "frontend"
    ):

        today = datetime.now(UTC).strftime("%Y-%m-%d")

        key = f"usage:{workflow_type}:{user_id}:{today}"

        current = await redis_client.get(key)

        return int(current) if current else 0









