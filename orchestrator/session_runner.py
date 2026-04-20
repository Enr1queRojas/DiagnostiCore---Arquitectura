# orchestrator/session_runner.py
"""Per-run Managed Agent session orchestration.

Reads agent_ids + env_id from config/managed_agents_config.json (written by
managed_agent_setup.py). For each agent call, creates a session, sends the
context as a user message (stream-first pattern), streams SSE events, and
returns the parsed JSON output.

Use asyncio.to_thread(runner.run_agent_session, ...) to parallelize A1-A6.
"""
import anthropic
import json
import logging
from pathlib import Path
from typing import Any

from orchestrator.exceptions import AgentOutputError, LLMError

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/managed_agents_config.json")


class SessionRunner:
    """Creates and drives one Managed Agent session per agent invocation."""

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        self._client = anthropic.Anthropic()
        self._config: dict = json.loads(config_path.read_text(encoding="utf-8"))

    def run_agent_session(
        self,
        agent_key: str,
        context: dict,
        run_id: str,
    ) -> dict[str, Any]:
        """Create a session, send context, stream output, return parsed JSON.

        Args:
            agent_key: One of A1-A10 or CB.
            context: Dict serialized as the user message (evidence + contract +
                     optional feedback). Agents' system prompts are on the Agent
                     object — do NOT duplicate them here.
            run_id:   Diagnostic run ID used for session title and logging.

        Returns:
            Parsed JSON dict from the agent's text response.

        Raises:
            LLMError: If session creation or stream I/O fails at the API level.
            AgentOutputError: If the accumulated text is not valid JSON.
        """
        agent_cfg = self._config["agents"][agent_key]
        env_id = self._config["environment_id"]

        try:
            session = self._client.beta.sessions.create(
                agent={"type": "agent", "id": agent_cfg["id"], "version": agent_cfg["version"]},
                environment_id=env_id,
                title=f"{run_id}_{agent_key}",
            )
        except anthropic.APIError as exc:
            raise LLMError(
                f"Session creation failed for {agent_key} (run={run_id}): {exc}"
            ) from exc

        logger.info("Session %s opened for %s (run=%s)", session.id, agent_key, run_id)
        return self._stream_session(session.id, agent_key, context)

    def _stream_session(
        self, session_id: str, agent_key: str, context: dict
    ) -> dict[str, Any]:
        """Open SSE stream, send user message, collect text, return parsed JSON.

        Stream-first pattern: stream is opened BEFORE events.send() so no
        early events are missed.
        """
        output_parts: list[str] = []

        try:
            with self._client.beta.sessions.stream(session_id=session_id) as stream:
                self._client.beta.sessions.events.send(
                    session_id=session_id,
                    events=[{
                        "type": "user.message",
                        "content": [{
                            "type": "text",
                            "text": json.dumps(context, ensure_ascii=False, indent=2),
                        }],
                    }],
                )
                for event in stream:
                    if event.type == "agent.message":
                        for block in event.content:
                            if block.type == "text":
                                output_parts.append(block.text)

                    elif event.type == "session.status_terminated":
                        logger.warning(
                            "Session %s terminated for %s", session_id, agent_key
                        )
                        break

                    elif event.type == "session.status_idle":
                        # requires_action = waiting on custom tool result; keep looping
                        if event.stop_reason.type != "requires_action":
                            break

        except anthropic.APIError as exc:
            raise LLMError(
                f"Stream error in session {session_id} ({agent_key}): {exc}"
            ) from exc

        raw = "".join(output_parts).strip()
        logger.debug(
            "Session %s (%s): received %d chars of output",
            session_id, agent_key, len(raw),
        )

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AgentOutputError(
                f"{agent_key} (session={session_id}) output is not valid JSON: {exc}\n"
                f"First 500 chars: {raw[:500]}"
            ) from exc
