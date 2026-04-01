"""
orchestrator/llm_client.py
===========================
Async wrapper around the Anthropic Messages API for DiagnostiCore.

Responsibilities:
  • Load agent system prompts from /agents/*.md
  • Issue sampling calls with retry logic for transient API errors
  • Map SDK exceptions to domain-specific LLMError variants
  • Enforce per-agent token budgets to prevent runaway costs

Usage:
    client = AsyncLLMClient(api_key="sk-ant-...")
    system_prompt = client.load_system_prompt("A1")
    raw_text = await client.sample("A1", system_prompt, messages=[...])
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Final

import anthropic
from opentelemetry.trace import Status, StatusCode

from orchestrator.exceptions import LLMError
from telemetry.tracing import get_tracer

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MODEL: Final[str] = "claude-sonnet-4-6"

# Token budgets per agent.
# Dimensional agents (A1-A6) produce compact JSON → 2 048 tokens is sufficient.
# Synthesis (A7) integrates 6 outputs + causal reasoning → needs more headroom.
# One-Pager (A8) writes executive prose + full markdown → largest budget.
TOKEN_BUDGETS: Final[dict[str, int]] = {
    "A1": 2048,
    "A2": 2048,
    "A3": 2048,
    "A4": 2048,
    "A5": 2048,
    "A6": 2048,
    "A7": 4096,
    "A8": 4096,
}

# Maps agent IDs to their prompt file names inside /agents/
AGENT_PROMPT_FILES: Final[dict[str, str]] = {
    "A1": "A1_estrategia.md",
    "A2": "A2_liderazgo.md",
    "A3": "A3_cultura.md",
    "A4": "A4_procesos.md",
    "A5": "A5_datos.md",
    "A6": "A6_tecnologia.md",
    "A7": "A7_sintesis.md",
    "A8": "A8_one_pager.md",
}

# Retry policy for rate-limit errors only.
# Other API errors (auth, bad request) are not retried — they are deterministic.
_MAX_RETRIES: Final[int] = 3
_BASE_BACKOFF_S: Final[float] = 2.0  # Seconds; doubles on each attempt


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────

class AsyncLLMClient:
    """
    Async wrapper around anthropic.AsyncAnthropic for DiagnostiCore agents.

    Thread-safety: This class holds no mutable state after __init__, so a
    single instance can be shared safely across concurrent coroutines.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        agents_dir: Path | None = None,
    ) -> None:
        """
        Args:
            api_key:    Anthropic API key. Must be set; never falls back to env
                        here — the caller (main.py) is responsible for that.
            model:      Model ID to use for all sampling calls.
            agents_dir: Directory that contains the agent *.md prompt files.
                        Defaults to <project_root>/agents/.
        """
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.agents_dir: Path = agents_dir or (
            Path(__file__).parent.parent / "agents"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def load_system_prompt(self, agent_id: str) -> str:
        """
        Reads the system prompt for the given agent from its .md file.

        The entire markdown file is used as the system prompt so that the full
        InnoVerse methodology, maturity scales, and output schemas are always
        in the model's context.

        Raises:
            LLMError: If the agent ID is unknown or the file is missing.
        """
        filename = AGENT_PROMPT_FILES.get(agent_id)
        if not filename:
            raise LLMError(
                f"Unknown agent ID '{agent_id}'. "
                f"Valid IDs: {list(AGENT_PROMPT_FILES)}",
                agent_id=agent_id,
            )

        prompt_path = self.agents_dir / filename
        if not prompt_path.exists():
            raise LLMError(
                f"System prompt file not found: {prompt_path}. "
                f"Ensure the /agents/ directory is intact.",
                agent_id=agent_id,
            )

        return prompt_path.read_text(encoding="utf-8")

    async def sample(
        self,
        agent_id: str,
        system_prompt: str,
        messages: list[dict],
    ) -> str:
        """
        Invokes the Anthropic Messages API and returns the model's raw text.

        Retry behaviour:
          - RateLimitError → exponential backoff, up to _MAX_RETRIES attempts.
          - APIConnectionError → fails immediately (no retry; likely infra issue).
          - APIStatusError → fails immediately (auth errors, bad requests are
            deterministic; retrying won't help).

        Args:
            agent_id:      Used for logging and token budget look-up.
            system_prompt: The agent's full markdown system prompt.
            messages:      Conversation history in Anthropic message format,
                           e.g. [{"role": "user", "content": "..."}].

        Returns:
            The text of the first content block in the response.

        Raises:
            LLMError: On unrecoverable API failures after all retries exhausted.
        """
        max_tokens = TOKEN_BUDGETS.get(agent_id, 2048)
        tracer = get_tracer()

        with tracer.start_as_current_span(
            "diagnosticore.llm.sample",
            attributes={
                "agent.id": agent_id,
                "llm.model": self.model,
                "llm.max_tokens": max_tokens,
            },
        ) as span:
            for attempt in range(1, _MAX_RETRIES + 1):
                span.set_attribute("llm.attempt", attempt)
                try:
                    logger.debug(
                        "LLM call | agent=%s | model=%s | attempt=%d/%d",
                        agent_id, self.model, attempt, _MAX_RETRIES,
                    )

                    response = await self._client.messages.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        system=system_prompt,
                        messages=messages,
                        temperature=0,  # Deterministic output — critical for JSON consistency
                    )

                    # Defensive check: the API always returns at least one block,
                    # but guard against future API changes.
                    if not response.content:
                        raise LLMError(
                            "Anthropic API returned an empty content array.",
                            agent_id=agent_id,
                            attempt=attempt,
                        )

                    raw_text: str = response.content[0].text
                    span.set_attribute("llm.input_tokens", response.usage.input_tokens)
                    span.set_attribute("llm.output_tokens", response.usage.output_tokens)
                    span.set_attribute("llm.stop_reason", response.stop_reason or "")
                    logger.info(
                        "LLM call complete | agent=%s | stop_reason=%s"
                        " | input_tokens=%d | output_tokens=%d",
                        agent_id,
                        response.stop_reason,
                        response.usage.input_tokens,
                        response.usage.output_tokens,
                    )
                    return raw_text

                except anthropic.RateLimitError as exc:
                    wait_s = _BASE_BACKOFF_S * (2 ** (attempt - 1))
                    logger.warning(
                        "Rate limit hit | agent=%s | attempt=%d/%d"
                        " | backing off %.1fs",
                        agent_id, attempt, _MAX_RETRIES, wait_s,
                    )
                    span.set_attribute("llm.rate_limited", True)
                    if attempt == _MAX_RETRIES:
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, "Rate limit exceeded"))
                        raise LLMError(
                            f"Anthropic rate limit exceeded after {_MAX_RETRIES} retries.",
                            agent_id=agent_id,
                            attempt=attempt,
                        ) from exc
                    await asyncio.sleep(wait_s)

                except anthropic.APIConnectionError as exc:
                    # Network-level failure — no point retrying immediately
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, "API connection failed"))
                    raise LLMError(
                        f"Connection to Anthropic API failed: {exc}",
                        agent_id=agent_id,
                        attempt=attempt,
                    ) from exc

                except anthropic.AuthenticationError as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, "Authentication failed"))
                    raise LLMError(
                        "Anthropic API key is invalid or expired. "
                        "Check ANTHROPIC_API_KEY.",
                        agent_id=agent_id,
                        attempt=attempt,
                    ) from exc

                except anthropic.APIStatusError as exc:
                    # Covers 4xx/5xx responses not handled above
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {exc.status_code}"))
                    raise LLMError(
                        f"Anthropic API error (HTTP {exc.status_code}): {exc.message}",
                        agent_id=agent_id,
                        attempt=attempt,
                    ) from exc

            # Unreachable — the loop always returns or raises — but makes mypy happy
            raise LLMError(  # pragma: no cover
                "Exhausted retry loop without result.",
                agent_id=agent_id,
                attempt=_MAX_RETRIES,
            )
