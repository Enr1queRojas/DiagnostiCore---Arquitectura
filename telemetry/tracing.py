"""
telemetry/tracing.py
=====================
OpenTelemetry tracing setup for DiagnostiCore.

Creates spans for the diagnostic pipeline hierarchy:

  diagnosticore.pipeline.run          (1 per full diagnostic)
    └── diagnosticore.agent.run       (8 total: A1-A6 concurrent, A7, A8)
          └── diagnosticore.llm.sample  (1-2 per agent: attempt + correction)

Span attributes (selected):
  run.id              — diagnostic run identifier
  agent.id            — A1 … A8
  agent.nivel_madurez — maturity level 1-5 (set on success)
  llm.model           — Anthropic model ID
  llm.input_tokens    — tokens consumed in the prompt
  llm.output_tokens   — tokens generated
  llm.attempt         — 1 = first call, 2 = self-correction round

Configuration (environment variables):
  OTEL_EXPORTER_OTLP_ENDPOINT   — OTLP HTTP endpoint (e.g. http://localhost:4318)
                                   When set, a BatchSpanProcessor sends spans there.
  OTEL_SERVICE_NAME              — Service name tag (default: "diagnosticore")
  DIAGNOSTICORE_OTEL_CONSOLE     — Set to "1" to echo spans to stdout (dev mode)

Usage:
    from telemetry.tracing import setup_telemetry, get_tracer

    setup_telemetry()          # call once at startup
    tracer = get_tracer()

    with tracer.start_as_current_span("my.operation") as span:
        span.set_attribute("key", "value")
        ...
"""

from __future__ import annotations

import logging
import os
from typing import Final

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_INSTRUMENTATION_SCOPE: Final[str] = "diagnosticore"
_DEFAULT_SERVICE_NAME: Final[str] = "diagnosticore"
_ENV_OTLP_ENDPOINT: Final[str] = "OTEL_EXPORTER_OTLP_ENDPOINT"
_ENV_SERVICE_NAME: Final[str] = "OTEL_SERVICE_NAME"
_ENV_CONSOLE: Final[str] = "DIAGNOSTICORE_OTEL_CONSOLE"

# Module-level TracerProvider — set once by setup_telemetry()
_provider: TracerProvider | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────

def setup_telemetry(
    service_name: str | None = None,
    otlp_endpoint: str | None = None,
    *,
    console_export: bool | None = None,
) -> None:
    """
    Initialise the OpenTelemetry TracerProvider and register it globally.

    Idempotent — calling it more than once is a no-op after the first call.

    Args:
        service_name:    Override OTEL_SERVICE_NAME (default: "diagnosticore").
        otlp_endpoint:   Override OTEL_EXPORTER_OTLP_ENDPOINT.
                         When provided, spans are forwarded to this OTLP/HTTP
                         collector (e.g. Jaeger, Tempo, Honeycomb, Datadog agent).
        console_export:  Override DIAGNOSTICORE_OTEL_CONSOLE.
                         True → print spans to stdout in addition to OTLP.
    """
    global _provider
    if _provider is not None:
        return  # Already initialised

    name = (
        service_name
        or os.environ.get(_ENV_SERVICE_NAME, "")
        or _DEFAULT_SERVICE_NAME
    )
    endpoint = otlp_endpoint or os.environ.get(_ENV_OTLP_ENDPOINT, "")
    use_console = (
        console_export
        if console_export is not None
        else os.environ.get(_ENV_CONSOLE, "") == "1"
    )

    resource = Resource(attributes={SERVICE_NAME: name})
    provider = TracerProvider(resource=resource)

    # ── OTLP exporter (optional) ──────────────────────────────────────────────
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            otlp_exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OpenTelemetry: OTLP exporter → %s", endpoint)
        except ImportError:
            logger.warning(
                "opentelemetry-exporter-otlp-proto-http is not installed. "
                "OTLP export disabled. "
                "Install with: pip install opentelemetry-exporter-otlp-proto-http"
            )

    # ── Console exporter (dev / debugging) ────────────────────────────────────
    if use_console:
        # SimpleSpanProcessor so spans appear immediately on stdout
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        logger.info("OpenTelemetry: console exporter enabled")

    if not endpoint and not use_console:
        logger.debug(
            "OpenTelemetry: no exporter configured — spans are recorded but not exported. "
            "Set OTEL_EXPORTER_OTLP_ENDPOINT or DIAGNOSTICORE_OTEL_CONSOLE=1 to export."
        )

    # Register as the global provider so third-party libs using otel APIs
    # (e.g. httpx instrumentation) also emit to the same backend.
    trace.set_tracer_provider(provider)
    _provider = provider
    logger.info("OpenTelemetry: TracerProvider initialised | service=%s", name)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_tracer() -> trace.Tracer:
    """
    Return the DiagnostiCore module tracer.

    Lazily calls setup_telemetry() with defaults if not yet initialised.
    This allows instrumented code to work correctly even when the host
    (main.py or a test) hasn't called setup_telemetry() explicitly.
    """
    if _provider is None:
        setup_telemetry()
    return trace.get_tracer(_INSTRUMENTATION_SCOPE)
