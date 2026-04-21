"""
orchestrator/contract_builder.py
==================================
Generates a diagnostic contract before launching dimensional agents (A1–A6).

The contract defines, per dimension:
  - evidencia_requerida:        which evidence sources the agent must use
  - evidencia_minima_nivel_3:   what A9 needs to see to accept a level-3+ assignment
  - antipatrones_prioritarios:  which of the 7 anti-patterns are most probable
                                given this client's industry and size
  - criterios_exito:            how A9 knows this dimension's output is ready

This is the "sprint contract" pattern from Anthropic's Harness Design article:
before each sprint, generator and evaluator negotiate what success looks like.

Public API:
    build_contract(diagnostico_id, client_info, available_evidence, runner)
        -> contract dict (also persisted to blackboard/contracts/)
    load_contract(diagnostico_id) -> dict
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orchestrator.session_runner import SessionRunner
from orchestrator import state_manager

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent
_CONTRACTS_DIR = _ROOT / "blackboard" / "contracts"
_CONFIG_DIR = _ROOT / "config"
_AGENTS_DIR = _ROOT / "agents"

DIMENSION_KEYS = [
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

def _load_antipatterns_summary() -> list[dict]:
    """Load simplified anti-pattern list for the contract prompt."""
    path = _CONFIG_DIR / "antipatterns.json"
    if not path.exists():
        path = _CONFIG_DIR / "antipatrones.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as fh:
        catalog = json.load(fh)
    return [
        {
            "id": ap["id"],
            "nombre": ap["nombre"],
            "prevalencia_pct": ap.get("prevalencia_pct", 0),
            "dimension_primaria": ap.get("dimension_primaria", ""),
            "dimensiones": ap.get("dimensiones", []),
        }
        for ap in catalog.get("antipatrones", [])
    ]


def _save_contract(diagnostico_id: str, contract: dict) -> str:
    """Persist the contract to disk. Returns relative path string."""
    _CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{diagnostico_id}_contract.json"
    path = _CONTRACTS_DIR / filename
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(contract, fh, ensure_ascii=False, indent=2)
    logger.info("Contract saved: %s", path)
    return f"blackboard/contracts/{filename}"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def build_contract(
    diagnostico_id: str,
    client_info: dict,
    available_evidence: list[str],
    runner: SessionRunner,
) -> dict[str, Any]:
    """
    Generate and persist a diagnostic contract for the given client.

    Args:
        diagnostico_id:     Unique run/diagnostic ID.
        client_info:        Dict with 'name', 'industry', 'size'.
        available_evidence: List of evidence source descriptions, e.g.
                            ["transcripcion_CEO", "cuestionario_TI", "auditoria_ERP"].
        runner:             Configured SessionRunner.

    Returns:
        The contract dict (also saved to blackboard/contracts/).
    """
    logger.info("═══ CONTRACT BUILDER | run=%s ═══", diagnostico_id)
    state_manager.update_pipeline_status(diagnostico_id, "contract_building")

    # ── Build context dict for the CB agent session ───────────────────────────
    context = {
        "diagnostico_id": diagnostico_id,
        "client": client_info,
        "available_evidence": available_evidence,
        "antipatterns_catalog_summary": _load_antipatterns_summary(),
        "dimension_keys": DIMENSION_KEYS,
        "instruccion": "Genera el contrato de diagnóstico. Responde ÚNICAMENTE con JSON válido.",
    }
    contract = await asyncio.to_thread(
        runner.run_agent_session, "CB", context, diagnostico_id
    )

    # ── Ensure required structure ─────────────────────────────────────────────
    contract.setdefault("diagnostico_id", diagnostico_id)
    contract.setdefault("client", client_info)
    contract.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    contract.setdefault("dimensions", {})
    for dim in DIMENSION_KEYS:
        contract["dimensions"].setdefault(dim, {
            "evidencia_requerida": available_evidence[:3],
            "evidencia_minima_nivel_3": "Evidencia de al menos 2 fuentes distintas",
            "antipatrones_prioritarios": [],
            "criterios_exito": "Output completo con justificación basada en evidencia",
        })

    # ── Persist ───────────────────────────────────────────────────────────────
    contract_path = _save_contract(diagnostico_id, contract)

    try:
        state_manager.update_contract(diagnostico_id, contract_path, "approved")
        state_manager.append_history(
            diagnostico_id, "contract_builder", "approved",
            f"contract at {contract_path}",
        )
    except Exception as exc:
        logger.warning("Could not update state after contract build: %s", exc)

    logger.info("Contract generated and approved | id=%s", diagnostico_id)
    return contract


def load_contract(diagnostico_id: str) -> dict:
    """
    Load a previously generated contract from disk.

    Returns an empty dict if no contract exists (non-fatal — agents run without it).
    """
    path = _CONTRACTS_DIR / f"{diagnostico_id}_contract.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
