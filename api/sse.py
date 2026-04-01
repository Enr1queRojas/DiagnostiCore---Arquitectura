"""
api/sse.py
===========
Server-Sent Events (SSE) event bus for DiagnostiCore real-time progress.

Architecture:
  RunEventBus is a module-level singleton that bridges the async orchestrator
  and the FastAPI SSE endpoint:

    orchestrator/agent_runner.py   →   event_bus.emit(run_id, type, data)
    api/app.py GET /stream         →   async for event in event_bus.subscribe(run_id)

  Each active SSE client gets its own asyncio.Queue[dict | None]. The sentinel
  value None signals the generator to close (pipeline finished or errored).

  No circular imports: this module imports only stdlib — the orchestrator
  imports from here, and the API layer imports from both.

Event schema (all fields are strings/primitives):
  {
    "type":      str,   # see EVENT_TYPES below
    "run_id":    str,
    "data":      dict,
    "timestamp": str    # ISO-8601 UTC
  }

Event types:
  phase_start    — a pipeline phase began (data: phase, agents[])
  agent_start    — a single agent was dispatched (data: agent_id)
  agent_done     — agent completed (data: agent_id, nivel_madurez?)
  agent_error    — agent failed (data: agent_id, error)
  pipeline_done  — all agents succeeded (data: run_id)
  pipeline_error — pipeline aborted (data: run_id, failed_agents[], error)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Final

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

EVENT_TYPES: Final[frozenset[str]] = frozenset({
    "phase_start",
    "agent_start",
    "agent_done",
    "agent_error",
    "pipeline_done",
    "pipeline_error",
})

# Maximum queued events per subscriber before older events are dropped.
# Protects against slow consumers stalling the orchestrator via put_nowait().
_MAX_QUEUE_SIZE: Final[int] = 256


# ─────────────────────────────────────────────────────────────────────────────
# Event bus
# ─────────────────────────────────────────────────────────────────────────────

class RunEventBus:
    """
    In-process pub/sub bus for diagnostic run progress events.

    One bus instance is shared across the entire application lifetime.
    Subscribers receive all events emitted for their run_id until the pipeline
    terminates (sentinel None is pushed) or the client disconnects.
    """

    def __init__(self) -> None:
        # run_id → list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    # ── Emit (called by orchestrator) ────────────────────────────────────────

    def emit(self, run_id: str, event_type: str, data: dict) -> None:
        """
        Publish an event to all active subscribers of *run_id*.

        Non-blocking: uses put_nowait(). If a subscriber's queue is full,
        that subscriber's oldest event is silently dropped (overrun warning
        logged) to prevent the orchestrator from stalling.

        Safe to call from any thread (asyncio event loop thread or otherwise)
        because put_nowait() is thread-safe for asyncio.Queue.
        """
        event = {
            "type": event_type,
            "run_id": run_id,
            "data": data,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

        queues = self._subscribers.get(run_id, [])
        for q in list(queues):  # snapshot to avoid mutation during iteration
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "SSE queue full for run %s — dropping oldest event to make room",
                    run_id,
                )
                # Drop the oldest item and retry once
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

        # When the pipeline terminates, push the sentinel to close all streams
        if event_type in ("pipeline_done", "pipeline_error"):
            self._push_sentinel(run_id)

    def _push_sentinel(self, run_id: str) -> None:
        """Push None to every subscriber queue to signal stream end."""
        for q in list(self._subscribers.get(run_id, [])):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass

    # ── Subscribe (called by FastAPI SSE endpoint) ───────────────────────────

    async def subscribe(self, run_id: str) -> AsyncGenerator[dict, None]:
        """
        Async generator that yields events for *run_id* until the pipeline ends
        or the client disconnects.

        Usage in FastAPI:
            async for event in event_bus.subscribe(run_id):
                yield {"event": event["type"], "data": json.dumps(event["data"])}
        """
        queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._subscribers.setdefault(run_id, []).append(queue)
        logger.debug("SSE subscriber registered | run=%s | total=%d",
                     run_id, len(self._subscribers[run_id]))

        try:
            while True:
                event = await queue.get()
                if event is None:
                    # Sentinel — pipeline finished
                    logger.debug("SSE stream closed by sentinel | run=%s", run_id)
                    return
                yield event
        except asyncio.CancelledError:
            # Client disconnected
            logger.debug("SSE client disconnected | run=%s", run_id)
        finally:
            self._unsubscribe(run_id, queue)

    def _unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        queues = self._subscribers.get(run_id, [])
        try:
            queues.remove(queue)
        except ValueError:
            pass
        if not queues:
            self._subscribers.pop(run_id, None)
        logger.debug("SSE subscriber removed | run=%s | remaining=%d",
                     run_id, len(self._subscribers.get(run_id, [])))

    # ── Introspection ────────────────────────────────────────────────────────

    def subscriber_count(self, run_id: str) -> int:
        """Number of active SSE subscribers for a run (useful for monitoring)."""
        return len(self._subscribers.get(run_id, []))

    def active_runs(self) -> list[str]:
        """Run IDs that currently have at least one active SSE subscriber."""
        return list(self._subscribers.keys())


# Module-level singleton — both orchestrator and api.app import this
event_bus = RunEventBus()
