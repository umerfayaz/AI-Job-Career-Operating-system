import os
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from backend.redis.redis_memory import redis_client
from  backend.observability.workflow_instance import metrics_collector
from backend.postgreSQL.models import User
from backend.postgreSQL.models import Job
from backend.postgreSQL.database import AsyncSessionLocal
from sqlalchemy import select, func
from datetime import datetime


logger = structlog.get_logger()

# Importing ADMIN Key, App Router, Lock

router = APIRouter(prefix="/admin", tags=["admin"])
ADMIN_API_KEY=os.getenv("ADMIN_API_KEY")

def verify_admin(x_admin_key: str = Header(None)):
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY is not configured")
    
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return True


# Admin Live endpoint to see production users
@router.get("/live")
async def admin_live_status(request: Request, _:bool = Depends(verify_admin)):

    active_websocket_connections = request.app.state.active_websocket_connections
    pending_workflows = request.app.state.pending_workflows
    event_bus = request.app.state.event_bus

    return {
        "status": "healthy",
        "active_websocket_users": len(active_websocket_connections),
        "pending_workflows": len(pending_workflows),
        "connected_event_clients": len(event_bus.connections),
        "server_time": datetime.now().isoformat(),
        "uptime": "Coming Soon"
    }



@router.get("/workflows")
async def admin_workflows( request: Request, _:bool = Depends(verify_admin)):

        pending_workflows = request.app.state.pending_workflows
        workflow_lock = request.app.state.workflow_lock

        with workflow_lock:
            workflows =  []

            for task_id, workflow in pending_workflows.items():
                state = workflow.get("initial_state", {})
                started_at = state.get("started_at")
                run_id = workflow.get("run_id") or state.get("run_id")

                workflows.append({
                    "task_id": task_id,
                    "run_id": run_id,
                    "user_id": state.get("user_id"),
                "status": state.get("status"),
                "workflow_type": state.get("workflow_type"),
                "started_at": state.get("started_at").isoformat() if started_at else None,
                "keywords": state.get("job_keywords", []),
                "location": state.get("job_location"),
                "email": state.get("user_email"),
                "experience_level": state.get("experience_level")
                })

            return {
                "status": "healthy",
                "total_pending_workflows": len(workflows),
                "workflows": workflows,
                "server_time": datetime.now().isoformat() 
            }

@router.get("/metrics")
async def admin_metrics(_:bool = Depends(verify_admin)):
    try:

        frontend_metrics = await metrics_collector.get_recent(
            "frontend_workflow",
            100
        )

        autonomous_metrics = await metrics_collector.get_recent(
            "autonomous_workflow",
            100
        )

        def summarize(metrics):
            if not metrics:
                return {
                    "runs": 0,
                    "success_rate": 0,
                    "avg_latency_ms": 0,
                    "latest_latency_ms": 0,
                    "fastest_latency_ms": 0,
                    "slowest_latency_ms": 0,
                    "failed_runs": 0 
                }

            successful = len([ m for m in metrics if m.get("status") == "success"])
            failed = len([m for m in metrics if m.get("status") == "failed"])

            latencies = [m.get("latency_ms", 0) for m in metrics]

            return {
                "runs": len(metrics),
                "success_rate": round((successful / len(metrics)) * 100, 2),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
                "latest_latency_ms": latencies[0],
                "fastest_latency_ms": min(latencies),
                "slowest_latency_ms": max(latencies),
                "failed_runs": failed 
            }

        return {
            "frontend_metrics": summarize(frontend_metrics),
            "autonomous_metrics": summarize(autonomous_metrics),
            "server_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.warning(f"Failed to get admin metrics:{e}")


@router.get("/system")
async def admin_system(request: Request, _:bool = Depends(verify_admin)):

    try:
        active_websocket_connections = request.app.state.active_websocket_connections
        event_bus = request.app.state.event_bus
        pending_workflows = request.app.state.pending_workflows
        redis_status = "unknown"

        try:
            pong = await redis_client.ping()
            redis_status = "healthy" if pong else "unhealthy"
        
        except Exception as e:
            redis_status = f"error:{str(e)}"

        return {
            "status": "healthy",
            "redis": redis_status,
            "active_websocket_users": len(active_websocket_connections),
            "event_bus_clients": len(event_bus.connections),
            "pending_workflows": len(pending_workflows),
            "server_time": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.warning(f"Failed to get admins system: {e}")

@router.get("/users")
async def admin_users(
    limit: int = 20,
    _:bool = Depends(verify_admin)
):

    try:
        async with AsyncSessionLocal() as session:
            total_stmt = select(func.count()).select_from(User)
            total_result = await session.execute(total_stmt)
            total_user = total_result.scalar() or 0

            users_stmt = (
                select(User).order_by(User.created_at.desc()).limit(limit)
            )

            user_result = await session.execute(users_stmt)
            users = user_result.scalars().all()

            return {
                "status": "healthy",
                "total_users": total_user,
                "recent_users": [
                    {
                        "user_id": user.user_id,
                        "email": getattr(user, "email", None),
                        "created_at": user.created_at.isoformat()
                            if getattr(user, "created_at", None) else None,
                        "last_active_at": user.last_active_at.isoformat()
                            if getattr(user, "last_active_at", None) else None                    
                    }
                    for user in users
                ],
                "server_time": datetime.now().isoformat()
            }
    
    except Exception as e:
        logger.warning(f"Failed to get admin users:{e}")

@router.get("/applications")
async def admin_application(limit: int = 20, _: bool = Depends(verify_admin)):
    async with AsyncSessionLocal() as session:
        total_stmt = select(func.count()).select_from(Job)
        total_result = await session.execute(total_stmt)
        total_jobs_tracked = total_result.scalar() or 0

        applied_stmt = (
            select(func.count())
            .select_from(Job)
            .where(Job.applied_at.is_not(None))
        )
        applied_result = await session.execute(applied_stmt)
        total_applications = applied_result.scalar() or 0

        recent_stmt = (
            select(Job)
            .where(Job.applied_at.is_not(None))
            .order_by(Job.applied_at.desc())
            .limit(limit)
        )

        recent_result = await session.execute(recent_stmt)
        recent_applications = recent_result.scalars().all()

        return {
            "status": "healthy",
            "total_jobs_tracked": total_jobs_tracked,
            "total_applications": total_applications,
            "recent_application_count": len(recent_applications),
            "recent_applications": [
                {
                    "job_id": app.job_id,
                    "user_id": app.user_id,
                    "job": app.job,
                    "company": app.company,
                    "status": app.status,
                    "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                    "outcome_at": app.outcome_at.isoformat() if app.outcome_at else None,
                    "source": app.source,
                    "followup_count": app.followup_count,
                    "last_followup_at": app.last_followup_at.isoformat()
                        if app.last_followup_at else None,
                }
                for app in recent_applications
            ],
            "server_time": datetime.now().isoformat()
        }




