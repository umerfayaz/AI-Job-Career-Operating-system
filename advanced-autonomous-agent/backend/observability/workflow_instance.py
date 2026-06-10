import os
from .workflow_metrics import WorkflowMetricsCollector


metrics_collector = WorkflowMetricsCollector(
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
)


