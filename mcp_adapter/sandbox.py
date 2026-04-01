"""
mcp_adapter/sandbox.py
=======================
Subprocess sandbox for executing DiagnostiCore Python tools in isolation.

Why a subprocess sandbox?
  The MCP Server receives tool-call requests from external clients. Running
  tool code in-process would mean a malformed input could crash the entire
  server process and bring down all active diagnostic runs. Delegating to a
  child subprocess provides:
    - Crash isolation: a tool that throws an unhandled exception dies in the
      child, not the server.
    - Timeout enforcement: asyncio.wait_for() + process.kill() guarantees no
      tool call can block the server indefinitely.
    - Resource limits: the child inherits OS-level resource limits that can be
      tightened per-deployment (ulimit, Windows Job Objects) without changes to
      this code.

Protocol:
  - Input:  single JSON object written to the child's stdin.
  - Output: single JSON object read from the child's stdout.
  - Errors: child writes a plain-text error message to stderr; sandbox wraps it
            in SandboxExecutionError and re-raises.

Timeout:
  Default is 30 seconds, configurable per call. Tune downward for production
  (tools are CPU-bound and should complete in < 1 second on any PYME dataset).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

# Default wall-clock timeout per tool invocation (seconds)
DEFAULT_TIMEOUT: Final[float] = 30.0

# Directory containing the tool scripts (resolved at import time)
_TOOLS_DIR: Final[Path] = Path(__file__).parent.parent / "tools"


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class SandboxError(Exception):
    """Base class for all sandbox failures."""


class SandboxTimeoutError(SandboxError):
    """The tool exceeded its allowed wall-clock time and was killed."""
    def __init__(self, tool: str, timeout: float) -> None:
        super().__init__(
            f"Tool '{tool}' timed out after {timeout}s and was killed. "
            f"Check for infinite loops or unexpectedly large inputs."
        )
        self.tool = tool
        self.timeout = timeout


class SandboxExecutionError(SandboxError):
    """The tool process exited with a non-zero code or wrote to stderr."""
    def __init__(self, tool: str, returncode: int, stderr_text: str) -> None:
        super().__init__(
            f"Tool '{tool}' exited with code {returncode}. "
            f"stderr: {stderr_text[:500]!r}"
        )
        self.tool = tool
        self.returncode = returncode
        self.stderr_text = stderr_text


# ─────────────────────────────────────────────────────────────────────────────
# Tool wrapper scripts
# ─────────────────────────────────────────────────────────────────────────────
# Each tool exposes a thin stdin→stdout JSON wrapper so the sandbox doesn't
# need to know about individual function signatures. These are generated
# at call time as a one-liner injected via -c, keeping the tool files clean.

_TOOL_RUNNERS: Final[dict[str, str]] = {
    "calcular_idd": """
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from tools.calcular_idd import calcular_idd
payload = json.load(sys.stdin)
result = calcular_idd(payload["scores"])
print(json.dumps(result, ensure_ascii=False))
""",
    "detectar_antipatrones": """
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from tools.detectar_antipatron import detectar_antipatrones
payload = json.load(sys.stdin)
result = detectar_antipatrones(
    payload["texto_evidencia"],
    payload.get("umbral_confianza", 0.5),
)
print(json.dumps(result, ensure_ascii=False))
""",
    "cuantificar_costo": """
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from tools.cuantificar_costo import CuantificadorCosto
payload = json.load(sys.stdin)
calc = CuantificadorCosto(payload.get("nombre_cliente", ""))
calc.desde_json(payload)
result = calc.calcular()
print(json.dumps(result, ensure_ascii=False))
""",
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def run_tool_sandboxed(
    tool_name: str,
    input_data: dict[str, Any],
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Execute a DiagnostiCore tool in an isolated subprocess.

    The tool receives *input_data* serialised as JSON on stdin and must return
    a single JSON object on stdout.

    Args:
        tool_name:   One of: "calcular_idd", "detectar_antipatrones",
                     "cuantificar_costo".
        input_data:  Dict payload forwarded to the tool as JSON stdin.
        timeout:     Wall-clock seconds before the child is killed.

    Returns:
        Parsed JSON dict from the tool's stdout.

    Raises:
        ValueError:              Unknown tool name.
        SandboxTimeoutError:     Tool exceeded timeout.
        SandboxExecutionError:   Tool exited non-zero or wrote to stderr.
        json.JSONDecodeError:    Tool produced non-JSON stdout (propagated raw).
    """
    if tool_name not in _TOOL_RUNNERS:
        raise ValueError(
            f"Unknown tool: '{tool_name}'. "
            f"Available: {sorted(_TOOL_RUNNERS)}"
        )

    runner_script = _TOOL_RUNNERS[tool_name].strip()
    input_json = json.dumps(input_data, ensure_ascii=False)

    logger.debug("Sandbox | tool=%s | input_bytes=%d", tool_name, len(input_json))

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", runner_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Run from repo root so relative imports resolve correctly
            cwd=str(_TOOLS_DIR.parent),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=input_json.encode()),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise SandboxTimeoutError(tool_name, timeout)

    except SandboxTimeoutError:
        raise
    except Exception as exc:
        raise SandboxError(
            f"Failed to launch subprocess for tool '{tool_name}': {exc}"
        ) from exc

    stderr_text = stderr_bytes.decode(errors="replace").strip()
    stdout_text = stdout_bytes.decode(errors="replace").strip()

    if proc.returncode != 0:
        raise SandboxExecutionError(tool_name, proc.returncode, stderr_text)

    if stderr_text:
        # Non-zero stderr on a successful exit means the tool printed warnings
        logger.warning("Sandbox | tool=%s | stderr: %s", tool_name, stderr_text[:300])

    logger.debug(
        "Sandbox | tool=%s | exit=%d | output_bytes=%d",
        tool_name, proc.returncode, len(stdout_text),
    )

    return json.loads(stdout_text)
