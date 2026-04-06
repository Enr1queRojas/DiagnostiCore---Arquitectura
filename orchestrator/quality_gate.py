"""
orchestrator/quality_gate.py
==============================
Executes the quality-gate evaluation (agent A9) for each dimensional output.

Architecture:
    quality_gate(diagnostico_id, dimension_key, dimensional_output, llm_client)
        1. Load maturity scale for the dimension from config/maturity_scales.json
        2. Load anti-pattern catalog from config/antipatterns.json
        3. Load contract criteria from blackboard/contracts/{id}_contract.json (if exists)
        4. Build A9 system prompt from agents/A9_quality_gate.md
        5. Invoke LLM with output + scale + antipatterns + contract
        6. Parse evaluation JSON (with one self-correction attempt)
        7. Save evaluation to blackboard/evaluations/{id}_{dim}_eval.json
        8. Update diagnostico-state.json (eval_passed, eval_path, status → evaluated)
        9. If FAIL: return feedback string for the dimensional agent to retry
       10. After 2 FAILs: raise QualityGateEscalationError (requires human review)

Raises:
    QualityGateEscalationError: Dimension failed quality gate twice.
    ValidationError:            A9 returned unparseable output.
    LLMError:                   Unrecoverable API failure.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orchestrator.exceptions import LLMError, OrchestratorError, ValidationError
from orchestrator.llm_client import AsyncLLMClient
from orchestrator import state_manager

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent
_AGENTS_DIR = _ROOT / "agents"
_CONFIG_DIR = _ROOT / "config"
_EVALUATIONS_DIR = _ROOT / "blackboard" / "evaluations"
_CONTRACTS_DIR = _ROOT / "blackboard" / "contracts"


# ─────────────────────────────────────────────────────────────────────────────
# Custom exception
# ─────────────────────────────────────────────────────────────────────────────

class QualityGateEscalationError(OrchestratorError):
    """
    Raised when a dimension fails quality-gate twice and requires human review.
    The diagnostic cannot proceed until a consultant resolves the issue.
    """
    def __init__(self, dimension_key: str, diagnostico_id: str, last_feedback: str):
        self.dimension_key = dimension_key
        self.diagnostico_id = diagnostico_id
        self.last_feedback = last_feedback
        super().__init__(
            f"Quality gate escalation: [{dimension_key}] failed 2 times for "
            f"run '{diagnostico_id}'. Human review required.\n"
            f"Last feedback: {last_feedback}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Config loaders
# ─────────────────────────────────────────────────────────────────────────────

def _load_maturity_scale(dimension_key: str) -> dict:
    """Load the maturity scale for the given dimension from config/maturity_scales.json."""
    path = _CONFIG_DIR / "maturity_scales.json"
    if not path.exists():
        logger.warning("maturity_scales.json not found — quality gate will run without scale reference")
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        scales = json.load(fh)
    return scales.get(dimension_key, scales.get("global", {}))


def _load_antipatterns(dimension_key: str) -> list[dict]:
    """Return anti-patterns relevant to the given dimension."""
    path = _CONFIG_DIR / "antipatterns.json"
    if not path.exists():
        # Fallback to legacy file
        path = _CONFIG_DIR / "antipatrones.json"
    if not path.exists():
        logger.warning("antipatterns.json not found — quality gate will skip anti-pattern verification")
        return []
    with open(path, "r", encoding="utf-8") as fh:
        catalog = json.load(fh)
    all_ap = catalog.get("antipatrones", [])
    # Filter to anti-patterns that should be checked for this dimension
    relevant = [
        ap for ap in all_ap
        if dimension_key in ap.get("dimensiones", [ap.get("dimension_primaria", "")])
    ]
    return relevant


def _load_contract_criteria(diagnostico_id: str, dimension_key: str) -> dict:
    """Load the dimension-specific contract criteria if a contract exists."""
    contract_path = _CONTRACTS_DIR / f"{diagnostico_id}_contract.json"
    if not contract_path.exists():
        return {}
    try:
        with open(contract_path, "r", encoding="utf-8") as fh:
            contract = json.load(fh)
        return contract.get("dimensions", {}).get(dimension_key, {})
    except Exception as exc:
        logger.warning("Could not load contract for %s: %s", diagnostico_id, exc)
        return {}


def _load_a9_prompt() -> str:
    """Load the A9 quality-gate system prompt from agents/A9_quality_gate.md."""
    path = _AGENTS_DIR / "A9_quality_gate.md"
    if not path.exists():
        raise FileNotFoundError(f"A9 quality gate prompt not found at {path}")
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# JSON extraction (same approach as agent_runner)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """Extract and parse JSON from raw LLM output."""
    text = raw.strip()
    for pattern in [r"```json\s*([\s\S]*?)\s*```", r"```\s*([\s\S]*?)\s*```", r"(\{[\s\S]*\})"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                continue
    raise ValidationError("A9 output could not be parsed as JSON", agent_id="A9")


def _validate_eval_output(data: dict) -> None:
    """Minimal validation of A9's evaluation output."""
    required = ["resultado", "scores", "feedback_para_agente"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValidationError(
            f"A9 evaluation missing required fields: {missing}",
            agent_id="A9",
        )
    if data.get("resultado") not in ("PASS", "FAIL"):
        raise ValidationError(
            f"A9 'resultado' must be 'PASS' or 'FAIL', got: {data.get('resultado')!r}",
            agent_id="A9",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Save evaluation to disk
# ─────────────────────────────────────────────────────────────────────────────

def _save_evaluation(diagnostico_id: str, dimension_key: str, eval_data: dict) -> str:
    """Persist evaluation JSON and return the file path."""
    _EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{diagnostico_id}_{dimension_key}_eval.json"
    path = _EVALUATIONS_DIR / filename
    eval_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(eval_data, fh, ensure_ascii=False, indent=2)
    logger.info("Evaluation saved: %s", path)
    return str(path.relative_to(_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# Core quality gate logic
# ─────────────────────────────────────────────────────────────────────────────

async def run_quality_gate(
    diagnostico_id: str,
    dimension_key: str,
    dimensional_output: dict[str, Any],
    llm_client: AsyncLLMClient,
) -> tuple[bool, str]:
    """
    Run A9 quality-gate evaluation for one dimensional output.

    Returns:
        (passed: bool, feedback: str)
            - passed=True means the output cleared the quality bar.
            - passed=False means the dimensional agent should retry with feedback.

    Raises:
        QualityGateEscalationError: Dimension has already been retried twice.
        ValidationError:            A9 returned unparseable output.
        LLMError:                   Unrecoverable API failure.
    """
    # ── Check retry count ─────────────────────────────────────────────────────
    try:
        state = state_manager.load_state(diagnostico_id)
        retry_count = state["dimensions"][dimension_key].get("retry_count", 0)
        if retry_count >= 2:
            last_eval = _get_last_feedback(diagnostico_id, dimension_key)
            raise QualityGateEscalationError(dimension_key, diagnostico_id, last_eval)
    except (FileNotFoundError, KeyError):
        retry_count = 0

    logger.info(
        "═══ QUALITY GATE | dim=%s | run=%s | retry=%d ═══",
        dimension_key, diagnostico_id, retry_count,
    )

    # ── Build inputs for A9 ───────────────────────────────────────────────────
    maturity_scale = _load_maturity_scale(dimension_key)
    antipatterns = _load_antipatterns(dimension_key)
    contract_criteria = _load_contract_criteria(diagnostico_id, dimension_key)
    system_prompt = _load_a9_prompt()

    eval_input = {
        "dimension_key": dimension_key,
        "client_id": diagnostico_id,
        "output_dimensional": dimensional_output,
        "maturity_scale": maturity_scale,
        "antipatterns_to_verify": antipatterns,
        "contract_criteria": contract_criteria,
    }

    user_message = (
        "Evalúa el siguiente output dimensional usando los criterios del quality-gate.\n\n"
        "<eval_input>\n"
        f"{json.dumps(eval_input, ensure_ascii=False, indent=2)}\n"
        "</eval_input>\n\n"
        "Retorna ÚNICAMENTE un objeto JSON válido con los campos del schema de output. "
        "Sin texto antes ni después del JSON."
    )

    messages = [{"role": "user", "content": user_message}]

    # ── Invoke A9 (with one self-correction attempt) ──────────────────────────
    raw_response = await llm_client.sample(
        agent_id="A9",
        system_prompt=system_prompt,
        messages=messages,
    )

    try:
        eval_data = _extract_json(raw_response)
        _validate_eval_output(eval_data)
    except (ValidationError, json.JSONDecodeError) as first_err:
        logger.warning("[A9] First parse failed (%s) — self-correcting", first_err)
        correction_messages = messages + [
            {"role": "assistant", "content": raw_response},
            {
                "role": "user",
                "content": (
                    f"Your previous response failed with: {first_err}\n"
                    "Return ONLY a valid JSON object — no text before or after it."
                ),
            },
        ]
        raw_response = await llm_client.sample(
            agent_id="A9",
            system_prompt=system_prompt,
            messages=correction_messages,
        )
        eval_data = _extract_json(raw_response)
        _validate_eval_output(eval_data)

    # ── Persist evaluation ────────────────────────────────────────────────────
    eval_path = _save_evaluation(diagnostico_id, dimension_key, eval_data)
    passed = eval_data["resultado"] == "PASS"
    feedback = eval_data.get("feedback_para_agente", "") if not passed else ""

    # ── Update state ──────────────────────────────────────────────────────────
    score_ponderado = eval_data.get("score_ponderado", 0.0)
    try:
        state_manager.update_dimension(
            diagnostico_id,
            dimension_key,
            {
                "eval_path": eval_path,
                "eval_passed": passed,
                "status": "evaluated" if passed else "complete",  # keep "complete" if needs retry
                "retry_count": retry_count + (0 if passed else 1),
            },
        )
        action = "eval_pass" if passed else "eval_fail"
        state_manager.append_history(
            diagnostico_id, "A9", action,
            f"dim={dimension_key} score={score_ponderado:.1f} passed={passed}",
        )
    except Exception as exc:
        logger.warning("Could not update state after quality gate: %s", exc)

    if passed:
        logger.info("[A9] PASS | dim=%s | score=%.1f", dimension_key, score_ponderado)
    else:
        logger.warning(
            "[A9] FAIL | dim=%s | score=%.1f | feedback=%s",
            dimension_key, score_ponderado, feedback[:100],
        )

    return passed, feedback


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_last_feedback(diagnostico_id: str, dimension_key: str) -> str:
    """Retrieve the last failure feedback from the most recent evaluation file."""
    filename = f"{diagnostico_id}_{dimension_key}_eval.json"
    path = _EVALUATIONS_DIR / filename
    if not path.exists():
        return "(no previous evaluation found)"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("feedback_para_agente", "(no feedback in evaluation file)")
    except Exception:
        return "(could not read evaluation file)"
