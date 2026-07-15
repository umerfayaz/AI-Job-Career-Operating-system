from datetime import datetime
from fastapi import HTTPException
from backend.redis.redis_memory import redis_client

async def check_workflow_limit(user_id: str, plan = "free"):
    daily_limit = 3 if plan == "free" else 25

    today = datetime.now().strftime("%Y-%m-%d")
    key = f"workflow_limit:{user_id}:{today}"

    current = await redis_client.get(key)
    current_count = int(current) if current else 0

    if current_count >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Daily workflow limit",
                "message": f"Free users can run {daily_limit} workflow runs per day. Upgrade to pro for more runs",
                "limit": daily_limit,
                "used": current_count,
                "remaining": 0,
                "plan": plan
            }
        )
    
    await redis_client.incr(key)
    await redis_client.expire(key, 86400)

    used = current_count + 1

    return {
        "limit": daily_limit,
        "used": used,
        "remaining": daily_limit - (current_count + 1),
        "plan": plan 
    }

