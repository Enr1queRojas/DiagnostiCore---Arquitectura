"""
mcp_adapter/tools_server.py
============================
MCP Server — DiagnostiCore Tools

Exposes the three DiagnostiCore Python tools as MCP tools via JSON-RPC 2.0.
Each tool is executed inside the subprocess sandbox (mcp_adapter/sandbox.py)
so a tool crash cannot take down the MCP server process.

Registered tools:
  calcular_idd           — Compute IDD (0-100) from 6 maturity scores.
  detectar_antipatrones  — Detect antipattern signals in free-form evidence text.
  cuantificar_costo      — Build a cost-of-inaction model from components.

MCP transport: stdio (default for local single-consultant deployments).
For multi-consultant deployments, swap `stdio` for `sse` in the run call.

Usage:
  # As a standalone server process (e.g. called by Claude Desktop):
  python -m mcp_adapter.tools_server

  # From within Python tests:
  from mcp_adapter.tools_server import create_tools_server
  server = create_tools_server()
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    TextContent,
    Tool,
)

from mcp_adapter.sandbox import (
    SandboxError,
    SandboxExecutionError,
    SandboxTimeoutError,
    run_tool_sandboxed,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Tool catalogue — MCP Tool definitions with JSON Schema input specs
# ─────────────────────────────────────────────────────────────────────────────

_TOOLS: list[Tool] = [
    Tool(
        name="calcular_idd",
        description=(
            "Calcula el Índice de Deuda Digital (IDD) en escala 0-100 a partir de los "
            "scores de madurez de las 6 dimensiones. "
            "0 = máxima deuda digital; 100 = sin deuda. "
            "Retorna IDD, clasificación por percentil, desglose por dimensión y barras visuales."
        ),
        inputSchema={
            "type": "object",
            "required": ["scores"],
            "properties": {
                "scores": {
                    "type": "object",
                    "description": "Scores de madurez 1-5 por dimensión.",
                    "required": [
                        "estrategia", "liderazgo", "cultura",
                        "procesos", "datos", "tecnologia",
                    ],
                    "properties": {
                        "estrategia":  {"type": "integer", "minimum": 1, "maximum": 5},
                        "liderazgo":   {"type": "integer", "minimum": 1, "maximum": 5},
                        "cultura":     {"type": "integer", "minimum": 1, "maximum": 5},
                        "procesos":    {"type": "integer", "minimum": 1, "maximum": 5},
                        "datos":       {"type": "integer", "minimum": 1, "maximum": 5},
                        "tecnologia":  {"type": "integer", "minimum": 1, "maximum": 5},
                    },
                    "additionalProperties": False,
                }
            },
        },
    ),
    Tool(
        name="detectar_antipatrones",
        description=(
            "Detecta los 7 anti-patrones organizacionales InnoVerse en texto libre "
            "(transcripciones de entrevistas, notas del consultor, cuestionarios). "
            "Retorna lista ordenada por confianza con nombre, riesgo, dimensión y prevalencia."
        ),
        inputSchema={
            "type": "object",
            "required": ["texto_evidencia"],
            "properties": {
                "texto_evidencia": {
                    "type": "string",
                    "minLength": 10,
                    "description": "Texto libre a analizar (puede incluir múltiples párrafos).",
                },
                "umbral_confianza": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.5,
                    "description": (
                        "Proporción mínima de señales textuales para confirmar un anti-patrón. "
                        "0.5 = al menos 50% de señales presentes."
                    ),
                },
            },
        },
    ),
    Tool(
        name="cuantificar_costo",
        description=(
            "Calcula el costo mensual y anual de inacción (Cost of Delay) aplicando los "
            "factores de conservadurismo InnoVerse: reducción ×70%, revenue ×50%. "
            "Acepta componentes de tipo ineficiencia_proceso, revenue_perdido, riesgo y costo_oculto."
        ),
        inputSchema={
            "type": "object",
            "required": ["componentes"],
            "properties": {
                "nombre_cliente": {
                    "type": "string",
                    "description": "Nombre del cliente para el reporte (opcional).",
                },
                "componentes": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["nombre", "tipo", "monto_mensual_bruto"],
                        "properties": {
                            "nombre": {
                                "type": "string",
                                "description": "Descripción corta del componente de costo.",
                            },
                            "tipo": {
                                "type": "string",
                                "enum": [
                                    "ineficiencia_proceso",
                                    "revenue_perdido",
                                    "riesgo",
                                    "costo_oculto",
                                ],
                            },
                            "monto_mensual_bruto": {
                                "type": "number",
                                "minimum": 0,
                                "description": "Monto mensual bruto en MXN antes del factor de conservadurismo.",
                            },
                            "descripcion": {"type": "string"},
                            "dimension_origen": {"type": "string"},
                            "evidencia": {"type": "string"},
                        },
                    },
                },
            },
        },
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Server factory
# ─────────────────────────────────────────────────────────────────────────────

def create_tools_server() -> Server:
    """
    Build and return a configured MCP Server instance for DiagnostiCore tools.

    The server handles:
      tools/list  — returns the _TOOLS catalogue above
      tools/call  — dispatches to run_tool_sandboxed() and formats the result
    """
    server = Server("diagnosticore-tools")

    @server.list_tools()
    async def handle_list_tools(_: ListToolsRequest) -> list[Tool]:
        logger.debug("tools/list requested — returning %d tools", len(_TOOLS))
        return _TOOLS

    @server.call_tool()
    async def handle_call_tool(request: CallToolRequest) -> list[TextContent]:
        tool_name = request.params.name
        arguments: dict[str, Any] = request.params.arguments or {}

        logger.info("tools/call | tool=%s | args_keys=%s", tool_name, list(arguments))

        # Validate tool exists (MCP SDK validates schema; this is an extra guard)
        known_names = {t.name for t in _TOOLS}
        if tool_name not in known_names:
            error_msg = (
                f"Unknown tool '{tool_name}'. "
                f"Available tools: {sorted(known_names)}"
            )
            logger.warning(error_msg)
            return [TextContent(type="text", text=_error_json(tool_name, error_msg))]

        try:
            result = await run_tool_sandboxed(tool_name, arguments)
            import json as _json
            return [TextContent(
                type="text",
                text=_json.dumps(result, ensure_ascii=False, indent=2),
            )]

        except SandboxTimeoutError as exc:
            logger.error("Sandbox timeout | tool=%s | %s", tool_name, exc)
            return [TextContent(type="text", text=_error_json(tool_name, str(exc)))]

        except SandboxExecutionError as exc:
            logger.error(
                "Sandbox execution error | tool=%s | rc=%d | stderr=%r",
                tool_name, exc.returncode, exc.stderr_text[:200],
            )
            return [TextContent(type="text", text=_error_json(tool_name, str(exc)))]

        except SandboxError as exc:
            logger.error("Sandbox error | tool=%s | %s", tool_name, exc)
            return [TextContent(type="text", text=_error_json(tool_name, str(exc)))]

        except Exception as exc:
            logger.exception("Unexpected error in tools/call | tool=%s", tool_name)
            return [TextContent(type="text", text=_error_json(tool_name, str(exc)))]

    return server


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _error_json(tool: str, message: str) -> str:
    """Format a structured JSON error response for tool call failures."""
    import json as _json
    return _json.dumps(
        {"error": True, "tool": tool, "message": message},
        ensure_ascii=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def _main() -> None:
    """Run the tools MCP server over stdio transport."""
    import asyncio  # noqa: F401 — imported for type clarity

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("DiagnostiCore Tools MCP Server starting (stdio transport)...")

    server = create_tools_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="diagnosticore-tools",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(_main())
