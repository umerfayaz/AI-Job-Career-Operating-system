from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
import structlog
import logging
import os

logger = structlog.get_logger()

def setup_observability(app):
    """Configure Opentelemetry tracing and structured loggong"""

    try:
        logger.warning("Starting Opentelemetry Obervability")
        
        # Setup Tracing
        provider = TracerProvider(
            resource=Resource.create({
                "service.name": "agentic-system"
            })
        )

        OTLP_ENDPOINT=os.getenv("OTLP_ENDPOINT", "http://localhost:4317")

        exporter = OTLPSpanExporter(
            endpoint=OTLP_ENDPOINT, 
            insecure=True
        )

        span_processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(span_processor)
        trace.set_tracer_provider(provider)
        tracer = trace.get_tracer(__name__)
        HTTPXClientInstrumentor().instrument()

        # Specially for track with FASTAPI Server 
        FastAPIInstrumentor.instrument_app(app)

        # Structure Logging
        structlog.configure(
            processors = [
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer()
            ],
            wrapper_class = structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory = structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False
        )

        return tracer
    except Exception as e:
        logger.warning("Error in Oberservability Opentelemetry",(e))
        
