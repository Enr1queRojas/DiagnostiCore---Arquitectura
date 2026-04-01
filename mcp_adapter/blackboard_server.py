"""
mcp_adapter/blackboard_server.py
=================================
MCP Resource Server — DiagnostiCore Blackboard

Exposes the run Blackboard as MCP Resources using a `blackboard://` URI scheme.
Each resource provides a live view of a specific section of the run JSON.

Resource URI scheme:
  blackboard://{run_id}/status           — Run state, agent completion table
  blackboard://{run_id}/evidencia        — Raw evidence transcriptions
  blackboard://{run_id}/dimension/{key}  — Single dimensional analysis result
  blackboard://{run_id}/sintesis         — A7 synthesis output
  blackboard://{run_id}/one_pager        — A8 final One-Pager

Design choices:
  - Resources are READ-ONLY. Writes always go through the Blackboard class
    directly to preserve validation, atomic-write, and error-registration logic.
  - Resources are re-read from disk on every request (no in-memory cache) to
    guarantee fresh data in multi-process deployments where other processes
    may be writing the file.
  - If the requested run file does not exist, the server returns a structured
    JSON error instead of crashing — this lets MCP clients display a friendly
    message rather than losing the connection.
  - Notification support: the server sends resource/updated notifications when
    a subscriber is registered and the blackboard file's mtime changes.
    The watcher loop runs as a background asyncio task.

Usage:
  python -m mcp_adapter.blackboard_server --runs-dir runs
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlparse

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    ListResourcesRequest,
    ListResourcesResult,
    ReadResourceRequest,
    ReadResourceResult,
    Resource,
    TextResourceContents,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_SCHEME: Final[str] = "blackboard"

# File-watcher polling interval (seconds)
_POLL_INTERVAL: Final[float] = 2.0

# Sub-paths and their human-readable descriptions
_RESOURCE_PATHS: Final[dict[str, str]] = {
    "status":    "Run state and agent completion table",
    "evidencia": "Raw evidence transcriptions (PII already filtered)",
    "sintesis":  "A7 synthesis: root causes, IDD, transformation roadmap",
    "one_pager": "A8 executive One-Pager",
}

# Dimensional sub-resource paths
_DIMENSION_KEYS: Final[list[str]] = [
    "A1_estrategia",
    "A2_liderazgo",
    "A3_cultura",
    "A4_procesos",
    "A5_datos",
    "A6_tecnologia",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _list_run_ids(runs_dir: Path) -> list[str]:
    """Return sorted run IDs (filename stems) from the runs directory."""
    if not runs_dir.exists():
        return []
    return sorted(
        p.stem for p in runs_dir.glob("*.json")
        if not p.name.startswith(".") and p.stem != ".gitkeep"
    )


def _load_run(runs_dir: Path, run_id: str) -> dict[str, Any] | None:
    """Load and parse a run JSON file. Returns None if not found."""
    path = runs_dir / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load run %s: %s", run_id, exc)
        return None


def _run_mtime(runs_dir: Path, run_id: str) -> float:
    """Return file modification time for the run JSON. 0.0 if file absent."""
    path = runs_dir / f"{run_id}.json"
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _resource_content(
    data: dict[str, Any],
    sub_path: str,
) -> str:
    """
    Extract and serialise the relevant section of the blackboard JSON.

    Args:
        data:     Full parsed blackboard JSON.
        sub_path: One of the _RESOURCE_PATHS keys or "dimension/<key>".

    Returns:
        JSON string of the requested section, or a structured error message.
    """
    if sub_path == "status":
        payload = {
            "run_id":   data.get("run_id"),
            "estado":   data.get("estado"),
            "cliente":  data.get("cliente"),
            "agentes_completados": data.get("metadatos", {}).get("agentes_completados", []),
            "errores":  data.get("metadatos", {}).get("errores", []),
            "timestamps": data.get("timestamps", {}),
        }

    elif sub_path == "evidencia":
        payload = data.get("evidencia", {})

    elif sub_path == "sintesis":
        payload = data.get("sintesis") or {"_note": "Synthesis not yet available"}

    elif sub_path == "one_pager":
        payload = data.get("one_pager") or {"_note": "One-Pager not yet available"}

    elif sub_path.startswith("dimension/"):
        dim_key = sub_path.split("/", 1)[1]
        dim_data = data.get("resultados_dimensionales", {}).get(dim_key)
        payload = dim_data or {"_note": f"Dimension '{dim_key}' not yet available"}

    else:
        payload = {"error": f"Unknown sub-path: '{sub_path}'"}

    return json.dumps(payload, ensure_ascii=False, indent=2)


def _uri(run_id: str, sub_path: str) -> str:
    return f"{_SCHEME}://{run_id}/{sub_path}"


# ─────────────────────────────────────────────────────────────────────────────
# Change notification watcher
# ─────────────────────────────────────────────────────────────────────────────

class _FileWatcher:
    """
    Background task that polls run files for mtime changes and triggers
    MCP resource/updated notifications when a subscriber is registered.
    """

    def __init__(self, server: Server, runs_dir: Path) -> None:
        self._server = server
        self._runs_dir = runs_dir
        self._last_mtimes: dict[str, float] = {}
        self._running = False

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._poll_loop(), name="blackboard-watcher")
        logger.debug("File watcher started (poll_interval=%.1fs)", _POLL_INTERVAL)

    async def stop(self) -> None:
        self._running = False

    async def _poll_loop(self) -> None:
        while self._running:
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                await self._check_for_changes()
            except Exception as exc:
                logger.warning("File watcher error: %s", exc)

    async def _check_for_changes(self) -> None:
        for run_id in _list_run_ids(self._runs_dir):
            current_mtime = _run_mtime(self._runs_dir, run_id)
            prev_mtime = self._last_mtimes.get(run_id, 0.0)

            if current_mtime != prev_mtime:
                self._last_mtimes[run_id] = current_mtime
                logger.debug("Change detected in run %s — sending notifications", run_id)
                await self._notify_all(run_id)

    async def _notify_all(self, run_id: str) -> None:
        """Send resource/updated for every sub-path of the changed run."""
        all_sub_paths = (
            list(_RESOURCE_PATHS.keys())
            + [f"dimension/{k}" for k in _DIMENSION_KEYS]
        )
        for sub_path in all_sub_paths:
            try:
                await self._server.request_context.session.send_resource_updated(
                    _uri(run_id, sub_path)
                )
            except Exception:
                # Notification failure is non-fatal — client may have disconnected
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Server factory
# ─────────────────────────────────────────────────────────────────────────────

def create_blackboard_server(runs_dir: str = "runs") -> Server:
    """
    Build and return a configured MCP Resource Server for the Blackboard.

    Args:
        runs_dir: Directory where run JSON files are stored.

    Returns:
        Configured mcp.Server instance (not yet running).
    """
    _runs_path = Path(runs_dir).resolve()
    server = Server("diagnosticore-blackboard")

    @server.list_resources()
    async def handle_list_resources(_: ListResourcesRequest) -> list[Resource]:
        """Enumerate all resources across all known runs."""
        resources: list[Resource] = []

        for run_id in _list_run_ids(_runs_path):
            # Static sub-paths
            for sub_path, description in _RESOURCE_PATHS.items():
                resources.append(Resource(
                    uri=_uri(run_id, sub_path),
                    name=f"{run_id} — {description}",
                    description=description,
                    mimeType="application/json",
                ))
            # Dimensional sub-paths
            for dim_key in _DIMENSION_KEYS:
                dim_label = dim_key.replace("_", " ").title()
                resources.append(Resource(
                    uri=_uri(run_id, f"dimension/{dim_key}"),
                    name=f"{run_id} — Dimension: {dim_label}",
                    description=f"Maturity analysis for {dim_label}",
                    mimeType="application/json",
                ))

        logger.debug("resources/list — returned %d resources", len(resources))
        return resources

    @server.read_resource()
    async def handle_read_resource(request: ReadResourceRequest) -> list[TextResourceContents]:
        uri_str = str(request.params.uri)
        logger.info("resources/read | uri=%s", uri_str)

        # Parse URI: blackboard://{run_id}/{sub_path}
        parsed = urlparse(uri_str)
        if parsed.scheme != _SCHEME:
            return [_error_resource(uri_str, f"Unsupported URI scheme: '{parsed.scheme}'")]

        run_id = parsed.netloc
        # Remove leading slash from path
        sub_path = parsed.path.lstrip("/")

        if not run_id:
            return [_error_resource(uri_str, "URI is missing run_id in host part.")]

        data = _load_run(_runs_path, run_id)
        if data is None:
            return [_error_resource(
                uri_str,
                f"Run '{run_id}' not found in '{_runs_path}'. "
                f"Available runs: {_list_run_ids(_runs_path)}",
            )]

        content = _resource_content(data, sub_path)
        return [TextResourceContents(uri=uri_str, mimeType="application/json", text=content)]

    return server


def _error_resource(uri: str, message: str) -> TextResourceContents:
    return TextResourceContents(
        uri=uri,
        mimeType="application/json",
        text=json.dumps({"error": True, "message": message}, ensure_ascii=False),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def _main(runs_dir: str = "runs") -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(
        "DiagnostiCore Blackboard MCP Server starting | runs_dir=%s (stdio transport)...",
        runs_dir,
    )

    server = create_blackboard_server(runs_dir)
    watcher = _FileWatcher(server, Path(runs_dir).resolve())

    async with stdio_server() as (read_stream, write_stream):
        await watcher.start()
        try:
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="diagnosticore-blackboard",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities={},
                    ),
                ),
            )
        finally:
            await watcher.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="DiagnostiCore Blackboard MCP Resource Server"
    )
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Directory containing run JSON files (default: runs/)",
    )
    args = parser.parse_args()

    asyncio.run(_main(runs_dir=args.runs_dir))
