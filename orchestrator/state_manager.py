"""
orchestrator/state_manager.py
==============================
Manages diagnostico-state.json — the session-persistence layer for DiagnostiCore v2.

Each new session of Claude Code starts without memory of prior work. This module
implements the equivalent of the `progress.txt + git log` pattern from Anthropic's
Harness Design article: a structured JSON artifact that carries the agent's prior
state forward into the next session.

Public API:
    load_state(diagnostico_id)           -> dict
    save_state(state)                    -> None
    init_state(diagnostico_id, client)   -> dict
    update_dimension(diagnostico_id, dimension_key, updates) -> None
    append_history(diagnostico_id, agent, action, detail)    -> None
    update_contract(diagnostico_id, path, status)            -> None
    update_synthesis(diagnostico_id, updates)                -> None
    update_onepager(diagnostico_id, updates)                 -> None
    get_next_pending(diagnostico_id)     -> str | None
    is_all_dimensions_complete(diagnostico_id)   -> bool
    is_all_dimensions_evaluated(diagnostico_id)  -> bool

File: blackboard/diagnostico-state.json
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_STATE_FILE = Path(__file__).parent.parent / "blackboard" / "diagnostico-state.json"

DIMENSION_KEYS = [
    "A1_estrategia",
    "A2_liderazgo",
    "A3_cultura",
    "A4_procesos",
    "A5_datos",
    "A6_tecnologia",
]

VALID_STATUSES = {
    "initialized",
    "contract_building",
    "contract_approved",
    "dimensions_running",
    "dimensions_complete",
    "quality_gate",
    "synthesis",
    "output",
    "evaluation",
    "delivered",
    "error",
}

VALID_DIMENSION_STATUSES = {"pending", "running", "complete", "evaluated", "failed"}


# ─────────────────────────────────────────────────────────────────────────────
# File locking (cross-platform)
# ─────────────────────────────────────────────────────────────────────────────

def _acquire_lock(lock_path: Path) -> Any:
    """Acquire an exclusive file lock. Returns the lock file handle."""
    lock_path.touch(exist_ok=True)
    if sys.platform == "win32":
        import msvcrt
        fh = open(lock_path, "r+b")
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        return fh
    else:
        import fcntl
        fh = open(lock_path, "r+b")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        return fh


def _release_lock(fh: Any) -> None:
    """Release a previously acquired file lock."""
    if sys.platform == "win32":
        import msvcrt
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
    fh.close()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_raw() -> dict:
    """Read state file without acquiring a lock (caller must hold lock)."""
    if not _STATE_FILE.exists():
        return {}
    with open(_STATE_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_raw(state: dict) -> None:
    """Write state file atomically via a temp file (caller must hold lock)."""
    tmp = _STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(_STATE_FILE)


def _blank_state(diagnostico_id: str, client: dict | None = None) -> dict:
    """Return a fresh state dict for a new diagnostic."""
    now = _now_iso()
    client = client or {}
    return {
        "_meta": {
            "schema_version": "2.0",
            "descripcion": "Estado del diagnóstico activo.",
        },
        "diagnostico_id": diagnostico_id,
        "client": {
            "name": client.get("name", ""),
            "industry": client.get("industry", ""),
            "size": client.get("size", ""),
        },
        "status": "initialized",
        "created_at": now,
        "updated_at": now,
        "contract": {"path": "", "status": "pending"},
        "dimensions": {
            key: {
                "status": "pending",
                "output_path": "",
                "eval_path": "",
                "score": None,
                "eval_passed": None,
                "retry_count": 0,
            }
            for key in DIMENSION_KEYS
        },
        "synthesis": {"status": "pending", "output_path": ""},
        "onepager": {
            "status": "pending",
            "output_path": "",
            "eval_path": "",
            "eval_passed": None,
            "retry_count": 0,
        },
        "history": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def load_state(diagnostico_id: str) -> dict:
    """
    Load the current state for the given diagnostico_id.

    Raises:
        FileNotFoundError: If no state file exists yet.
        ValueError: If the stored state belongs to a different diagnostico_id.
    """
    if not _STATE_FILE.exists():
        raise FileNotFoundError(
            f"No state file found at {_STATE_FILE}. "
            "Call init_state() to create a new diagnostic."
        )
    state = _read_raw()
    stored_id = state.get("diagnostico_id", "")
    if stored_id and stored_id != diagnostico_id:
        raise ValueError(
            f"State file contains diagnostico_id='{stored_id}', "
            f"but requested '{diagnostico_id}'. "
            "Call init_state() to start a new diagnostic."
        )
    return state


def save_state(state: dict) -> None:
    """Persist the full state dict to disk with file locking."""
    lock_path = _STATE_FILE.with_suffix(".lock")
    fh = _acquire_lock(lock_path)
    try:
        state["updated_at"] = _now_iso()
        _write_raw(state)
        logger.debug("State saved | id=%s | status=%s", state.get("diagnostico_id"), state.get("status"))
    finally:
        _release_lock(fh)


def init_state(diagnostico_id: str, client: dict | None = None) -> dict:
    """
    Initialize a fresh state for a new diagnostic, overwriting any previous state.

    Args:
        diagnostico_id: Unique ID, e.g. "COMPOLAT_20260406" or "DX-2026-001"
        client: Optional dict with 'name', 'industry', 'size' keys.

    Returns:
        The newly created state dict (also persisted to disk).
    """
    state = _blank_state(diagnostico_id, client)
    save_state(state)
    logger.info("New diagnostic state initialized | id=%s", diagnostico_id)
    return state


def update_dimension(
    diagnostico_id: str,
    dimension_key: str,
    updates: dict,
) -> None:
    """
    Apply partial updates to a single dimension entry.

    Args:
        diagnostico_id: Must match the stored state.
        dimension_key: One of DIMENSION_KEYS (e.g. "A1_estrategia").
        updates: Dict with any subset of {status, output_path, eval_path,
                 score, eval_passed, retry_count}.
    """
    if dimension_key not in DIMENSION_KEYS:
        raise ValueError(f"Unknown dimension_key: {dimension_key!r}. Valid: {DIMENSION_KEYS}")

    lock_path = _STATE_FILE.with_suffix(".lock")
    fh = _acquire_lock(lock_path)
    try:
        state = _read_raw()
        _assert_id(state, diagnostico_id)
        state["dimensions"][dimension_key].update(updates)
        state["updated_at"] = _now_iso()
        _write_raw(state)
        logger.debug(
            "Dimension updated | id=%s | dim=%s | updates=%s",
            diagnostico_id, dimension_key, updates,
        )
    finally:
        _release_lock(fh)


def update_contract(diagnostico_id: str, path: str, status: str) -> None:
    """Update the contract path and approval status."""
    lock_path = _STATE_FILE.with_suffix(".lock")
    fh = _acquire_lock(lock_path)
    try:
        state = _read_raw()
        _assert_id(state, diagnostico_id)
        state["contract"]["path"] = path
        state["contract"]["status"] = status
        state["updated_at"] = _now_iso()
        if status == "approved":
            state["status"] = "contract_approved"
        _write_raw(state)
        logger.info("Contract updated | id=%s | status=%s", diagnostico_id, status)
    finally:
        _release_lock(fh)


def update_synthesis(diagnostico_id: str, updates: dict) -> None:
    """Apply partial updates to the synthesis block."""
    lock_path = _STATE_FILE.with_suffix(".lock")
    fh = _acquire_lock(lock_path)
    try:
        state = _read_raw()
        _assert_id(state, diagnostico_id)
        state["synthesis"].update(updates)
        state["updated_at"] = _now_iso()
        _write_raw(state)
    finally:
        _release_lock(fh)


def update_onepager(diagnostico_id: str, updates: dict) -> None:
    """Apply partial updates to the onepager block."""
    lock_path = _STATE_FILE.with_suffix(".lock")
    fh = _acquire_lock(lock_path)
    try:
        state = _read_raw()
        _assert_id(state, diagnostico_id)
        state["onepager"].update(updates)
        state["updated_at"] = _now_iso()
        _write_raw(state)
    finally:
        _release_lock(fh)


def update_pipeline_status(diagnostico_id: str, new_status: str) -> None:
    """Advance the top-level pipeline status."""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status!r}. Valid: {VALID_STATUSES}")
    lock_path = _STATE_FILE.with_suffix(".lock")
    fh = _acquire_lock(lock_path)
    try:
        state = _read_raw()
        _assert_id(state, diagnostico_id)
        state["status"] = new_status
        state["updated_at"] = _now_iso()
        _write_raw(state)
        logger.info("Pipeline status → %s | id=%s", new_status, diagnostico_id)
    finally:
        _release_lock(fh)


def append_history(
    diagnostico_id: str,
    agent: str,
    action: str,
    detail: str = "",
) -> None:
    """Append an event to the diagnostic history log."""
    lock_path = _STATE_FILE.with_suffix(".lock")
    fh = _acquire_lock(lock_path)
    try:
        state = _read_raw()
        _assert_id(state, diagnostico_id)
        state["history"].append(
            {
                "timestamp": _now_iso(),
                "agent": agent,
                "action": action,
                "detail": detail,
            }
        )
        state["updated_at"] = _now_iso()
        _write_raw(state)
    finally:
        _release_lock(fh)


def get_next_pending(diagnostico_id: str) -> str | None:
    """
    Return the dimension_key of the next dimension whose status is 'pending',
    or None if all dimensions have been started or completed.
    """
    state = load_state(diagnostico_id)
    for key in DIMENSION_KEYS:
        if state["dimensions"][key]["status"] == "pending":
            return key
    return None


def is_all_dimensions_complete(diagnostico_id: str) -> bool:
    """Return True if all 6 dimensions have status 'complete' or 'evaluated'."""
    state = load_state(diagnostico_id)
    return all(
        state["dimensions"][k]["status"] in ("complete", "evaluated")
        for k in DIMENSION_KEYS
    )


def is_all_dimensions_evaluated(diagnostico_id: str) -> bool:
    """Return True if all 6 dimensions have passed quality-gate (eval_passed=True)."""
    state = load_state(diagnostico_id)
    return all(
        state["dimensions"][k]["eval_passed"] is True
        for k in DIMENSION_KEYS
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internal assertion
# ─────────────────────────────────────────────────────────────────────────────

def _assert_id(state: dict, diagnostico_id: str) -> None:
    stored = state.get("diagnostico_id", "")
    if stored and stored != diagnostico_id:
        raise ValueError(
            f"ID mismatch: stored='{stored}', requested='{diagnostico_id}'"
        )
