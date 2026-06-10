from datetime import datetime
import redis
import json
import structlog
from dataclasses import dataclass, asdict

logger = structlog.get_logger()

@dataclass
class WorkflowMetrics:
    workflow_type: str
    task_id: str
    run_id: str
    status: str
    user_id: str
    latency_ms: float
    jobs_found: int
    matched_jobs: int
    confidence_score: float
    timestamp: float

class WorkflowMetricsCollector:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)
    
    async def record_workflow(self, metrics: WorkflowMetrics):
        logger.warning(f"Storing workflow_type={metrics.workflow_type}")

        key = f"workflow_metrics:{metrics.workflow_type}:{metrics.task_id}:{metrics.user_id}"

        logger.warning(f"Redis key = workflow_metrics:{metrics.workflow_type}")

        self.redis.set(
            key,
            json.dumps(asdict(metrics)),
            ex= 60 * 60 * 24 * 7
        )

        self.redis.lpush(
            f"workflow_metrics:{metrics.workflow_type}:{metrics.user_id}",
            json.dumps(asdict(metrics))
        )
    
    async def get_recent(self, workflow_type: str, limit: int = 100, user_id: str | None=None):
        data = self.redis.lrange(f"workflow_metrics:{workflow_type}:{user_id}", 0, limit - 1)
        return [json.loads(x) for x in data]






