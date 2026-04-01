"""
mcp_adapter — Model Context Protocol adapter layer for DiagnostiCore.

Fase 2 components:
  pii_filter   — Anonymize Mexican PII from evidence before any LLM call
  sandbox      — Run tools in an isolated subprocess with timeout
  tools_server — MCP Server: calcular_idd, detectar_antipatrones, cuantificar_costo
  blackboard_server — MCP Resource Server: exposes run state via blackboard:// URIs
"""

from mcp_adapter.pii_filter import FilterResult, filter_pii
from mcp_adapter.sandbox import SandboxError, SandboxExecutionError, SandboxTimeoutError, run_tool_sandboxed

__all__ = [
    "filter_pii",
    "FilterResult",
    "run_tool_sandboxed",
    "SandboxError",
    "SandboxTimeoutError",
    "SandboxExecutionError",
]
