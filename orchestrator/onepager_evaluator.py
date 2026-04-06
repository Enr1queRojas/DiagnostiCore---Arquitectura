"""
orchestrator/onepager_evaluator.py
====================================
Executes the One-Pager evaluation (agent A10) after A8 generates the output.

Architecture:
    run_onepager_evaluation(diagnostico_id, onepager_output, llm_client)
        1. Load acceptance criteria from config/acceptance_criteria.json
        2. Load A10 system prompt from agents/A10_onepager_eval.md
        3. Invoke A10 with the One-Pager + criteria
        4. Parse evaluation JSON (with one self-correction attempt)
        5. Save evaluation to blackboard/onepager/{id}_eval.json
        6. Update diagnostico-state.json (onepager.eval_passed, eval_path, status)
        7. Return (passed, feedback) tuple

    On second failure: raises OnePagerEscalationError (human review required)

Raises:
    OnePagerEscalationError: One-Pager failed quality check twice.
    ValidationError:         A10 returned unparseable output.
    LLMError:                Unrecoverable API failure.
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
_ONEPAGER_DIR = _ROOT / "blackboard" / "onepager"


# ─────────────────────────────────────────────────────────────────────────────
# Custom exception
# ─────────────────────────────────────────────────────────────────────────────

class OnePagerEscalationError(OrchestratorError):
    """
    Raised when the One-Pager fails the quality check twice.
    Requires consultant review before it can be delivered to the client.
    """
    def __init__(self, diagnostico_id: str, last_feedback: str):
        self.diagnostico_id = diagnostico_id
        self.last_feedback = last_feedback
        super().__init__(
            f"One-Pager escalation: run '{diagnostico_id}' failed A10 evaluation twice. "
            f"Consultant review required.\n"
            f"Last feedback: {last_feedback}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_acceptance_criteria() -> list[dict]:
    """Load the 8-item acceptance checklist from config/acceptance_criteria.json."""
    path = _CONFIG_DIR / "acceptance_criteria.json"
    if not path.exists():
        logger.warning("acceptance_criteria.json not found — A10 will evaluate without criteria")
        return []
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("criterios", [])


def _load_a10_prompt() -> str:
    """Load the A10 system prompt."""
    path = _AGENTS_DIR / "A10_onepager_eval.md"
    if not path.exists():
        raise FileNotFoundError(f"A10 prompt not found at {path}")
    return path.read_text(encoding="utf-8")


def _extract_json(raw: str) -> dict:
    """Extract and parse JSON from raw LLM text."""
    text = raw.strip()
    for pattern in [r"```json\s*([\s\S]*?)\s*```", r"```\s*([\s\S]*?)\s*```", r"(\{[\s\S]*\})"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                continue
    raise ValidationError("A10 output could not be parsed as JSON", agent_id="A10")


def _validate_a10_output(data: dict) -> None:
    """Ensure A10's evaluation has required fields."""
    required = ["resultado", "criterios_evaluados"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValidationError(
            f"A10 evaluation missing required fields: {missing}",
            agent_id="A10",
        )
    if data.get("resultado") not in ("PASS", "FAIL"):
        raise ValidationError(
            f"A10 'resultado' must be 'PASS' or 'FAIL', got: {data.get('resultado')!r}",
            agent_id="A10",
        )


def _save_evaluation(diagnostico_id: str, eval_data: dict) -> str:
    """Persist A10 evaluation to blackboard/onepager/ and return relative path."""
    _ONEPAGER_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{diagnostico_id}_onepager_eval.json"
    path = _ONEPAGER_DIR / filename
    eval_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(eval_data, fh, ensure_ascii=False, indent=2)
    logger.info("One-Pager evaluation saved: %s", path)
    return f"blackboard/onepager/{filename}"


def _get_last_feedback(diagnostico_id: str) -> str:
    """Retrieve the last failure feedback from the evaluation file."""
    filename = f"{diagnostico_id}_onepager_eval.json"
    path = _ONEPAGER_DIR / filename
    if not path.exists():
        return "(no previous evaluation found)"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("feedback_consolidado", "(no feedback in evaluation)")
    except Exception:
        return "(could not read evaluation file)"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def run_onepager_evaluation(
    diagnostico_id: str,
    onepager_output: dict[str, Any],
    llm_client: AsyncLLMClient,
) -> tuple[bool, str]:
    """
    Run A10 evaluation on the One-Pager generated by A8.

    Returns:
        (passed: bool, feedback: str)
            passed=True  → One-Pager is approved for client delivery.
            passed=False → A8 should regenerate with the provided feedback.

    Raises:
        OnePagerEscalationError: One-Pager has already been rejected twice.
        ValidationError:         A10 returned unparseable output.
        LLMError:                Unrecoverable API failure.
    """
    # ── Check retry count ─────────────────────────────────────────────────────
    try:
        state = state_manager.load_state(diagnostico_id)
        retry_count = state["onepager"].get("retry_count", 0)
        if retry_count >= 2:
            raise OnePagerEscalationError(diagnostico_id, _get_last_feedback(diagnostico_id))
    except (FileNotFoundError, KeyError):
        retry_count = 0

    logger.info(
        "═══ ONE-PAGER EVAL (A10) | run=%s | retry=%d ═══",
        diagnostico_id, retry_count,
    )

    # ── Build inputs for A10 ──────────────────────────────────────────────────
    criteria = _load_acceptance_criteria()
    system_prompt = _load_a10_prompt()

    eval_input = {
        "client_id": diagnostico_id,
        "onepager_output": onepager_output,
        "acceptance_criteria": criteria,
    }

    user_message = (
        "Evalúa el siguiente One-Pager usando el checklist de criterios de aceptación.\n\n"
        "<eval_input>\n"
        f"{json.dumps(eval_input, ensure_ascii=False, indent=2)}\n"
        "</eval_input>\n\n"
        "Retorna ÚNICAMENTE un objeto JSON válido con los campos del schema de output. "
        "Sin texto antes ni después del JSON."
    )

    messages = [{"role": "user", "content": user_message}]

    # ── Invoke A10 (with one self-correction attempt) ─────────────────────────
    raw_response = await llm_client.sample(
        agent_id="A10",
        system_prompt=system_prompt,
        messages=messages,
    )

    try:
        eval_data = _extract_json(raw_response)
        _validate_a10_output(eval_data)
    except (ValidationError, json.JSONDecodeError) as first_err:
        logger.warning("[A10] First parse failed (%s) — self-correcting", first_err)
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
            agent_id="A10",
            system_prompt=system_prompt,
            messages=correction_messages,
        )
        eval_data = _extract_json(raw_response)
        _validate_a10_output(eval_data)

    # ── Persist evaluation ────────────────────────────────────────────────────
    eval_path = _save_evaluation(diagnostico_id, eval_data)
    passed = eval_data["resultado"] == "PASS"
    feedback = eval_data.get("feedback_consolidado", "") if not passed else ""
    failed_criteria = eval_data.get("criterios_fallidos", [])

    # ── Update state ──────────────────────────────────────────────────────────
    try:
        state_manager.update_onepager(
            diagnostico_id,
            {
                "eval_path": eval_path,
                "eval_passed": passed,
                "status": "approved" if passed else "generated",
                "retry_count": retry_count + (0 if passed else 1),
            },
        )
        if passed:
            state_manager.update_pipeline_status(diagnostico_id, "delivered")
        action = "eval_pass" if passed else "eval_fail"
        detail = f"passed={passed}"
        if not passed:
            detail += f" failed_criteria={failed_criteria}"
        state_manager.append_history(diagnostico_id, "A10", action, detail)
    except Exception as exc:
        logger.warning("Could not update state after One-Pager evaluation: %s", exc)

    if passed:
        logger.info("[A10] One-Pager APPROVED | run=%s", diagnostico_id)
    else:
        logger.warning(
            "[A10] One-Pager REJECTED | run=%s | failed=%s | feedback=%s",
            diagnostico_id, failed_criteria, feedback[:100],
        )

    return passed, feedback
