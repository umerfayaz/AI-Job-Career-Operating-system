from opentelemetry import trace
from typing import Dict
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
import structlog
import logging


def setup_observability():
    """Configure Opentelemetry tracing and structured loggong"""

    # Setup Tracing
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(__name__)

    # ADD Exporters

    span_processor = BatchSpanProcessor(ConsoleSpanExporter())
    trace.get_tracer_provider().add_span_processor(span_processor)


    # Instrument HTTP Clients

    HTTPXClientInstrumentor().instrument()


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
