"""
orchestrator/ollama_runner.py
==============================
Drop-in replacement for SessionRunner that routes agent calls to a local
Ollama model instead of Anthropic Managed Agents.

Public API is identical to SessionRunner — pass an OllamaSessionRunner
wherever a SessionRunner is expected (duck typing, no base class required).

Usage:
    from orchestrator.ollama_runner import OllamaSessionRunner

    runner = OllamaSessionRunner()          # uses defaults below
    results = await run_full_pipeline(run_id, runner)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import ollama

from orchestrator.exceptions import AgentOutputError, LLMError

logger = logging.getLogger(__name__)

_AGENTS_DIR = Path(__file__).parent.parent / "agents"

_AGENT_FILE_MAP: dict[str, str] = {
    "A1":  "A1_estrategia",
    "A2":  "A2_liderazgo",
    "A3":  "A3_cultura",
    "A4":  "A4_procesos",
    "A5":  "A5_datos",
    "A6":  "A6_tecnologia",
    "A7":  "A7_sintesis",
    "A8":  "A8_one_pager",
    "A9":  "A9_quality_gate",
    "A10": "A10_onepager_eval",
    "A11": "A11_reporte_completo",
    "CB":  "CB_contract_builder",
}

_DEFAULT_HOST    = "https://llm.innoversesolutions.com.mx"
_DEFAULT_API_KEY = "fb531057a3278afd0ea488ce8dc4f9d2f8fafd51b867b4de6c4744db70416656"
_DEFAULT_MODEL   = "gemma4:12b"


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_system_prompt(agent_key: str) -> str:
    """Return the system prompt for agent_key from agents/*.md."""
    stem = _AGENT_FILE_MAP.get(agent_key)
    if stem:
        path = _AGENTS_DIR / f"{stem}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    # Fallback: first file that starts with the agent key
    matches = sorted(_AGENTS_DIR.glob(f"{agent_key}*.md"))
    if matches:
        return matches[0].read_text(encoding="utf-8")
    logger.warning("No system prompt found for agent %s — proceeding with empty prompt", agent_key)
    return ""


def _extract_json(raw: str) -> dict[str, Any]:
    """
    Extract and parse the first JSON object from the model's text response.

    Handles three common formats from chat models:
      1. ```json ... ```   — markdown JSON fenced block
      2. ``` ... ```       — generic fenced block
      3. bare { ... }      — raw JSON (ideal case)
    """
    text = raw.strip()

    m = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        return json.loads(m.group(1).strip())

    m = re.search(r"```\s*([\s\S]*?)\s*```", text)
    if m:
        return json.loads(m.group(1).strip())

    m = re.search(r"(\{[\s\S]*\})", text)
    if m:
        return json.loads(m.group(1).strip())

    return json.loads(text)


# ─────────────────────────────────────────────────────────────────────────────
# Public runner
# ─────────────────────────────────────────────────────────────────────────────

class OllamaSessionRunner:
    """
    Ollama-backed runner with the same interface as SessionRunner.

    Args:
        host:    Base URL of the Ollama proxy.
        api_key: Value sent as X-Ollama-Proxy-Key header.
        model:   Ollama model tag, e.g. "gemma4:12b".
    """

    def __init__(
        self,
        *,
        host: str = _DEFAULT_HOST,
        api_key: str = _DEFAULT_API_KEY,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        self._model = model
        self._client = ollama.Client(
            host=host,
            headers={"X-Ollama-Proxy-Key": api_key},
        )
        logger.info(
            "OllamaSessionRunner ready | model=%s | host=%s",
            model, host,
        )

    def run_agent_session(
        self,
        agent_key: str,
        context: dict,
        run_id: str,
    ) -> dict[str, Any]:
        """
        Call the Ollama model for one agent turn and return parsed JSON.

        Args:
            agent_key: One of A1–A11 or CB.
            context:   Dict that becomes the user message (evidence + contract +
                       optional quality-gate feedback). Mirrors what SessionRunner
                       serialises before sending to the Managed Agent session.
            run_id:    Diagnostic run ID (for logging only).

        Returns:
            Parsed JSON dict from the model's response.

        Raises:
            LLMError:         On any Ollama API or network failure.
            AgentOutputError: If the response cannot be parsed as a JSON dict.
        """
        system_prompt = _load_system_prompt(agent_key)
        user_message = json.dumps(context, ensure_ascii=False, indent=2)

        logger.info(
            "─── Ollama call | agent=%s | run=%s | model=%s ───",
            agent_key, run_id, self._model,
        )

        try:
            response = self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
            )
        except Exception as exc:
            raise LLMError(
                f"Ollama API error for {agent_key} (run={run_id}): {exc}"
            ) from exc

        raw: str = response["message"]["content"]
        logger.debug(
            "Ollama response | agent=%s | run=%s | chars=%d",
            agent_key, run_id, len(raw),
        )

        if not raw.strip():
            raise LLMError(
                f"Ollama returned empty response for {agent_key} (run={run_id})",
                agent_id=agent_key,
            )

        try:
            return _extract_json(raw)
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            raise AgentOutputError(
                f"{agent_key} (run={run_id}) response is not valid JSON: {exc}\n"
                f"First 500 chars: {raw[:500]}",
                agent_id=agent_key,
            ) from exc
