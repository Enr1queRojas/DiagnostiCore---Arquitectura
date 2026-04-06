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
    build_contract(diagnostico_id, client_info, available_evidence, llm_client)
        -> contract dict (also persisted to blackboard/contracts/)
    load_contract(diagnostico_id) -> dict
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orchestrator.llm_client import AsyncLLMClient
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
# Contract builder system prompt (inline — no separate agent file needed)
# ─────────────────────────────────────────────────────────────────────────────

_CONTRACT_SYSTEM_PROMPT = """\
Eres el arquitecto de diagnóstico de InnoVerse. Tu trabajo es generar un contrato
de diagnóstico específico para el cliente antes de que los agentes dimensionales
analicen la evidencia.

El contrato define para cada dimensión (A1–A6):
1. qué evidencia deben usar los agentes (dado lo que está disponible)
2. qué necesita ver el quality-gate para aprobar un nivel 3 o superior
3. cuáles anti-patrones son más probables dado el sector e industria del cliente
4. criterios de éxito específicos para este cliente

El contrato permite que el evaluador (A9) y el generador (A1–A6) tengan
expectativas alineadas ANTES de que comience el análisis.

OUTPUT REQUERIDO: JSON con esta estructura exacta:
{
  "diagnostico_id": "...",
  "client": { "name": "...", "industry": "...", "size": "..." },
  "generated_at": "ISO 8601",
  "dimensions": {
    "A1_estrategia": {
      "evidencia_requerida": ["fuente1", "fuente2"],
      "evidencia_minima_nivel_3": "qué evidencia mínima justifica nivel 3",
      "antipatrones_prioritarios": ["id_antipatron_1", "id_antipatron_2"],
      "criterios_exito": "criterio específico de éxito para este cliente y dimensión"
    },
    "A2_liderazgo": { ... },
    "A3_cultura": { ... },
    "A4_procesos": { ... },
    "A5_datos": { ... },
    "A6_tecnologia": { ... }
  }
}

Ajusta los criterios al contexto específico del cliente. Una empresa de manufactura
de 200 empleados tendrá criterios distintos a una fintech de 15 empleados.
"""

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


def _build_contract_user_message(
    diagnostico_id: str,
    client_info: dict,
    available_evidence: list[str],
) -> str:
    antipatterns = _load_antipatterns_summary()
    payload = {
        "diagnostico_id": diagnostico_id,
        "client": client_info,
        "available_evidence": available_evidence,
        "antipatterns_catalog_summary": antipatterns,
        "dimension_keys": DIMENSION_KEYS,
    }
    return (
        "Genera el contrato de diagnóstico para el siguiente cliente.\n\n"
        "<contract_input>\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "</contract_input>\n\n"
        "Retorna ÚNICAMENTE el JSON del contrato. Sin texto antes ni después."
    )


def _save_contract(diagnostico_id: str, contract: dict) -> str:
    """Persist the contract to disk. Returns relative path string."""
    _CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{diagnostico_id}_contract.json"
    path = _CONTRACTS_DIR / filename
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(contract, fh, ensure_ascii=False, indent=2)
    logger.info("Contract saved: %s", path)
    return f"blackboard/contracts/{filename}"


def _extract_json(raw: str) -> dict:
    """Extract JSON dict from raw LLM text."""
    import re
    text = raw.strip()
    for pattern in [r"```json\s*([\s\S]*?)\s*```", r"```\s*([\s\S]*?)\s*```", r"(\{[\s\S]*\})"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not extract JSON from contract builder response: {raw[:300]}")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def build_contract(
    diagnostico_id: str,
    client_info: dict,
    available_evidence: list[str],
    llm_client: AsyncLLMClient,
) -> dict[str, Any]:
    """
    Generate and persist a diagnostic contract for the given client.

    Args:
        diagnostico_id:     Unique run/diagnostic ID.
        client_info:        Dict with 'name', 'industry', 'size'.
        available_evidence: List of evidence source descriptions, e.g.
                            ["transcripcion_CEO", "cuestionario_TI", "auditoria_ERP"].
        llm_client:         Configured AsyncLLMClient.

    Returns:
        The contract dict (also saved to blackboard/contracts/).
    """
    logger.info("═══ CONTRACT BUILDER | run=%s ═══", diagnostico_id)
    state_manager.update_pipeline_status(diagnostico_id, "contract_building")

    user_message = _build_contract_user_message(diagnostico_id, client_info, available_evidence)
    messages = [{"role": "user", "content": user_message}]

    # ── First attempt ─────────────────────────────────────────────────────────
    raw_response = await llm_client.sample(
        agent_id="contract_builder",
        system_prompt=_CONTRACT_SYSTEM_PROMPT,
        messages=messages,
    )

    try:
        contract = _extract_json(raw_response)
    except ValueError as first_err:
        logger.warning("Contract builder first parse failed: %s — retrying", first_err)
        correction_messages = messages + [
            {"role": "assistant", "content": raw_response},
            {
                "role": "user",
                "content": (
                    f"Your previous response failed to parse as JSON: {first_err}\n"
                    "Return ONLY a valid JSON object — no text before or after it."
                ),
            },
        ]
        raw_response = await llm_client.sample(
            agent_id="contract_builder",
            system_prompt=_CONTRACT_SYSTEM_PROMPT,
            messages=correction_messages,
        )
        contract = _extract_json(raw_response)

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
