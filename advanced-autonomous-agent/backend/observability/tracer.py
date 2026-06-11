import structlog
from opentelemetry import trace
from backend.config.settings import Settings

settings = Settings()
logger = structlog.get_logger()

if settings.JAEGER_ENABLED and settings.OTLP_ENDPOINT:
    tracer = trace.get_tracer("agentic_system")

else:
    logger.warning("Jaeger Disabled")
    tracer = trace.get_tracer("agentic_system")

