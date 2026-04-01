"""
telemetry — OpenTelemetry instrumentation for DiagnostiCore.

Provides tracing spans for the entire diagnostic pipeline:
  pipeline  → agent  → LLM call  → blackboard write
"""

from telemetry.tracing import get_tracer, setup_telemetry

__all__ = ["setup_telemetry", "get_tracer"]
