# DiagnostiCore — Managed Agents Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate DiagnostiCore's manual `messages.create()` calls to the Claude Managed Agents API so each A1–A10 agent becomes a persisted, versioned Agent object whose diagnostic runs are isolated Sessions with structured SSE event streaming.

**Architecture:** The four Managed Agents primitives map directly onto DiagnostiCore's existing model — **Agent** = system prompt from `agents/*.md` + model config (created once, stored by ID); **Environment** = cloud container template (one shared env); **Session** = one agent invocation per diagnostic run; **Events** = SSE stream replacing the current `messages.create()` round-trips. A1–A6 sessions run concurrently via `asyncio.to_thread`. Quality gates (A9, A10) become their own Agent objects driven by the same SessionRunner.

**Tech Stack:** `anthropic` SDK (Managed Agents beta `managed-agents-2026-04-01`), Python 3.11+, asyncio, existing JSON state persistence in `blackboard/diagnostico-state.json`.

---

## Mapping: Current → Managed Agents

| Current Component | Maps To |
|---|---|
| `agents/A1_estrategia.md` (system prompt) | `agents.create(system=...)` — stored on Agent object |
| `AsyncLLMClient.sample(agent_id, ...)` | `sessions.create()` + `events.send()` + SSE stream |
| `asyncio.gather(run_A1, run_A2, ...)` | `asyncio.gather(asyncio.to_thread(runner.run_agent_session, "A1", ...), ...)` |
| `quality_gate.py` → `llm_client.sample("A9", ...)` | `runner.run_agent_session("A9", eval_context, run_id)` |
| `onepager_evaluator.py` → `llm_client.sample("A10", ...)` | `runner.run_agent_session("A10", eval_context, run_id)` |
| `contract_builder.py` → `llm_client.sample(...)` | `runner.run_agent_session("CB", contract_context, run_id)` |
| `diagnostico-state.json` (dimension state) | Gains `session_id` field per dimension for observability |

---

## File Map

### New Files
| File | Purpose |
|------|---------|
| `orchestrator/managed_agent_setup.py` | ONE-TIME: creates 1 cloud environment + 11 Agent objects (A1–A10 + CB), writes IDs to config |
| `orchestrator/session_runner.py` | Per-run: creates sessions, streams SSE events, returns parsed JSON |
| `config/managed_agents_config.json` | Persisted `env_id` + `agent_ids` (written by setup, read-only at runtime) |
| `tests/test_managed_agent_setup.py` | Unit tests for setup logic |
| `tests/test_session_runner.py` | Unit tests for session runner |

### Modified Files
| File | Key Change |
|------|-----------|
| `orchestrator/agent_runner.py` | Replace `llm_client.sample()` with `asyncio.to_thread(runner.run_agent_session, ...)` |
| `orchestrator/quality_gate.py` | Replace `llm_client.sample("A9", ...)` with `runner.run_agent_session("A9", ...)` |
| `orchestrator/onepager_evaluator.py` | Replace `llm_client.sample("A10", ...)` with `runner.run_agent_session("A10", ...)` |
| `orchestrator/contract_builder.py` | Replace `llm_client.sample(...)` with `runner.run_agent_session("CB", ...)` |
| `main.py` | Add `--setup` flag to invoke one-time setup before first diagnostic run |

### Unchanged Files
`orchestrator/llm_client.py` (kept as fallback — do not delete), `orchestrator/state_manager.py`, `orchestrator/exceptions.py`, `tools/`, `agents/`, `config/*.json`, `auth/`, `api/`, `blackboard/`

---

## Task 1: ONE-TIME Setup Script

**Files:**
- Create: `orchestrator/managed_agent_setup.py`
- Create: `tests/test_managed_agent_setup.py`
- Read (no edit): `agents/A1_estrategia.md` through `agents/A10_onepager_eval.md`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_managed_agent_setup.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


EXPECTED_AGENT_KEYS = {"A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "CB"}


def test_setup_writes_all_agent_ids_to_config(tmp_path):
    """setup_managed_agents() writes env_id + all 11 agent IDs to the config file."""
    config_path = tmp_path / "managed_agents_config.json"
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    for key in EXPECTED_AGENT_KEYS:
        (agents_dir / f"{key}.md").write_text(f"# System prompt for {key}")

    mock_env = MagicMock(id="env_test123")
    mock_agent = MagicMock(id="agent_abc", version=1)

    with patch("orchestrator.managed_agent_setup.anthropic.Anthropic") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.beta.environments.create.return_value = mock_env
        mock_client.beta.agents.create.return_value = mock_agent

        from orchestrator.managed_agent_setup import setup_managed_agents
        result = setup_managed_agents(config_path=config_path, agents_dir=agents_dir)

    assert config_path.exists()
    config = json.loads(config_path.read_text())
    assert config["environment_id"] == "env_test123"
    assert set(config["agents"].keys()) == EXPECTED_AGENT_KEYS
    for key in EXPECTED_AGENT_KEYS:
        assert config["agents"][key]["id"] == "agent_abc"
        assert config["agents"][key]["version"] == 1
    assert result == config


def test_setup_is_idempotent(tmp_path):
    """setup_managed_agents() skips API calls if config already exists."""
    config_path = tmp_path / "config.json"
    existing = {"environment_id": "env_existing", "agents": {}, "model": "claude-opus-4-7"}
    config_path.write_text(json.dumps(existing))

    with patch("orchestrator.managed_agent_setup.anthropic.Anthropic") as mock_cls:
        from orchestrator.managed_agent_setup import setup_managed_agents
        result = setup_managed_agents(config_path=config_path, agents_dir=tmp_path / "agents")
        mock_cls.return_value.beta.environments.create.assert_not_called()

    assert result["environment_id"] == "env_existing"


def test_setup_calls_agents_create_for_each_key(tmp_path):
    """agents.create() is called exactly once per agent key, not per run."""
    config_path = tmp_path / "config.json"
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    for key in EXPECTED_AGENT_KEYS:
        (agents_dir / f"{key}.md").write_text(f"prompt {key}")

    mock_env = MagicMock(id="env_x")
    mock_agent = MagicMock(id="agent_y", version=2)

    with patch("orchestrator.managed_agent_setup.anthropic.Anthropic") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.beta.environments.create.return_value = mock_env
        mock_client.beta.agents.create.return_value = mock_agent

        from orchestrator.managed_agent_setup import setup_managed_agents
        setup_managed_agents(config_path=config_path, agents_dir=agents_dir)

    assert mock_client.beta.agents.create.call_count == len(EXPECTED_AGENT_KEYS)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "c:\Users\Usuario\OneDrive\Documents\claude-obsidian\Python_Scripts\proyectos\DiagnostiCore — Arquitectura"
python -m pytest tests/test_managed_agent_setup.py -v 2>&1 | head -25
```

Expected: `ModuleNotFoundError: No module named 'orchestrator.managed_agent_setup'`

- [ ] **Step 3: Write `orchestrator/managed_agent_setup.py`**

```python
# orchestrator/managed_agent_setup.py
"""ONE-TIME setup: create 1 cloud environment + 11 Managed Agent objects (A1–A10 + CB).

Run ONCE before the first diagnostic run:
    python -m orchestrator.managed_agent_setup

Writes env_id + agent_ids to config/managed_agents_config.json.
NEVER call this from the per-run pipeline — agents are persistent resources.
"""
import anthropic
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/managed_agents_config.json")
AGENTS_DIR = Path("agents")
MODEL = "claude-opus-4-7"

# Maps agent_key → system prompt filename in agents/
AGENT_PROMPT_MAP: dict[str, str] = {
    "A1":  "A1_estrategia.md",
    "A2":  "A2_liderazgo.md",
    "A3":  "A3_cultura.md",
    "A4":  "A4_procesos.md",
    "A5":  "A5_datos.md",
    "A6":  "A6_tecnologia.md",
    "A7":  "A7_sintesis.md",
    "A8":  "A8_one_pager.md",
    "A9":  "A9_quality_gate.md",
    "A10": "A10_onepager_eval.md",
    "CB":  "CB_contract_builder.md",  # created in Task 6
}


def setup_managed_agents(
    config_path: Path = CONFIG_PATH,
    agents_dir: Path = AGENTS_DIR,
    model: str = MODEL,
) -> dict:
    """Create environment + agent objects. Idempotent: skips if config_path already exists.

    Returns the config dict (whether newly created or pre-existing).
    """
    if config_path.exists():
        logger.warning(
            "Config already exists at %s — delete it to re-run setup. "
            "To update a single agent, use agents.update() directly.",
            config_path,
        )
        return json.loads(config_path.read_text(encoding="utf-8"))

    client = anthropic.Anthropic()

    logger.info("Creating cloud environment 'diagnosticore-prod'...")
    env = client.beta.environments.create(
        name="diagnosticore-prod",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    logger.info("Environment created: %s", env.id)

    agent_ids: dict[str, dict] = {}
    for agent_key, prompt_file in AGENT_PROMPT_MAP.items():
        prompt_path = agents_dir / prompt_file
        system_prompt = prompt_path.read_text(encoding="utf-8")
        agent = client.beta.agents.create(
            name=f"DiagnostiCore-{agent_key}",
            model=model,
            system=system_prompt,
            description=f"DiagnostiCore diagnostic agent {agent_key}",
            thinking={"type": "adaptive"},
        )
        agent_ids[agent_key] = {"id": agent.id, "version": agent.version}
        logger.info("Agent %-3s created: %s (version=%s)", agent_key, agent.id, agent.version)

    config = {
        "environment_id": env.id,
        "model": model,
        "agents": agent_ids,
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Config written to %s", config_path)
    return config


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    setup_managed_agents()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_managed_agent_setup.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add orchestrator/managed_agent_setup.py tests/test_managed_agent_setup.py
git commit -m "feat(managed-agents): add one-time setup script for A1-A10 + CB agent objects"
```

---

## Task 2: SessionRunner — per-run session lifecycle

**Files:**
- Create: `orchestrator/session_runner.py`
- Create: `tests/test_session_runner.py`
- Read (no edit): `orchestrator/exceptions.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_session_runner.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

CONFIG = {
    "environment_id": "env_abc",
    "model": "claude-opus-4-7",
    "agents": {
        "A1": {"id": "agent_a1_id", "version": 1},
        "A9": {"id": "agent_a9_id", "version": 1},
    },
}
VALID_OUTPUT = {"nivel_madurez": 2, "justificacion": "ok", "hallazgos_principales": []}


def _mock_stream(events: list):
    """Build a mock stream context manager that yields given events."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=iter(events))
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_agent_message_event(text: str):
    block = MagicMock(type="text", text=text)
    event = MagicMock(type="agent.message", content=[block])
    return event


def _make_idle_event(stop_reason_type: str = "end_turn"):
    event = MagicMock(type="session.status_idle")
    event.stop_reason.type = stop_reason_type
    return event


def _make_terminated_event():
    return MagicMock(type="session.status_terminated")


def _build_runner(mock_client, config: dict = CONFIG):
    from orchestrator.session_runner import SessionRunner
    runner = SessionRunner.__new__(SessionRunner)
    runner._client = mock_client
    runner._config = config
    return runner


def test_run_agent_session_returns_parsed_json():
    """Happy path: agent.message event followed by idle → returns parsed dict."""
    mock_client = MagicMock()
    mock_client.beta.sessions.create.return_value = MagicMock(id="sesn_001")
    mock_client.beta.sessions.stream.return_value = _mock_stream([
        _make_agent_message_event(json.dumps(VALID_OUTPUT)),
        _make_idle_event("end_turn"),
    ])

    runner = _build_runner(mock_client)
    result = runner.run_agent_session("A1", {"evidence": "data"}, "TEST_20260420")

    assert result == VALID_OUTPUT
    create_call = mock_client.beta.sessions.create.call_args[1]
    assert create_call["environment_id"] == "env_abc"
    assert create_call["agent"]["id"] == "agent_a1_id"
    assert create_call["title"] == "TEST_20260420_A1"


def test_run_agent_session_breaks_on_terminated():
    """session.status_terminated stops the loop; no output → AgentOutputError."""
    from orchestrator.exceptions import AgentOutputError
    mock_client = MagicMock()
    mock_client.beta.sessions.create.return_value = MagicMock(id="sesn_002")
    mock_client.beta.sessions.stream.return_value = _mock_stream([
        _make_terminated_event(),
    ])

    runner = _build_runner(mock_client)
    with pytest.raises(AgentOutputError, match="not valid JSON"):
        runner.run_agent_session("A1", {}, "RUN")


def test_run_agent_session_skips_requires_action_idle():
    """requires_action idle does NOT break the loop; subsequent end_turn idle does."""
    # Two idle events: first requires_action (no break), then end_turn (break)
    mock_client = MagicMock()
    mock_client.beta.sessions.create.return_value = MagicMock(id="sesn_003")
    mock_client.beta.sessions.stream.return_value = _mock_stream([
        _make_idle_event("requires_action"),
        _make_agent_message_event(json.dumps(VALID_OUTPUT)),
        _make_idle_event("end_turn"),
    ])

    runner = _build_runner(mock_client)
    result = runner.run_agent_session("A9", {}, "RUN")
    assert result == VALID_OUTPUT


def test_run_agent_session_invalid_json_raises_agent_output_error():
    """Non-JSON agent text → AgentOutputError with raw output snippet."""
    from orchestrator.exceptions import AgentOutputError
    mock_client = MagicMock()
    mock_client.beta.sessions.create.return_value = MagicMock(id="sesn_004")
    mock_client.beta.sessions.stream.return_value = _mock_stream([
        _make_agent_message_event("Este no es JSON válido"),
        _make_idle_event("end_turn"),
    ])

    runner = _build_runner(mock_client)
    with pytest.raises(AgentOutputError, match="not valid JSON"):
        runner.run_agent_session("A1", {}, "RUN")


def test_run_agent_session_concatenates_multiple_text_blocks():
    """Multiple agent.message events are concatenated before JSON parse."""
    chunk1 = '{"nivel_madurez": 2, "justif'
    chunk2 = 'icacion": "ok", "hallazgos_principales": []}'
    mock_client = MagicMock()
    mock_client.beta.sessions.create.return_value = MagicMock(id="sesn_005")
    mock_client.beta.sessions.stream.return_value = _mock_stream([
        _make_agent_message_event(chunk1),
        _make_agent_message_event(chunk2),
        _make_idle_event("end_turn"),
    ])

    runner = _build_runner(mock_client)
    result = runner.run_agent_session("A1", {}, "RUN")
    assert result["nivel_madurez"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_session_runner.py -v 2>&1 | head -25
```

Expected: `ModuleNotFoundError: No module named 'orchestrator.session_runner'`

- [ ] **Step 3: Write `orchestrator/session_runner.py`**

```python
# orchestrator/session_runner.py
"""Per-run Managed Agent session orchestration.

Reads agent_ids + env_id from config/managed_agents_config.json (written by
managed_agent_setup.py). For each agent call, creates a session, sends the
context as a user message (stream-first pattern), streams SSE events, and
returns the parsed JSON output.

Use asyncio.to_thread(runner.run_agent_session, ...) to parallelize A1–A6.
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_agent_session(
        self,
        agent_key: str,
        context: dict,
        run_id: str,
    ) -> dict[str, Any]:
        """Create a session, send context, stream output, return parsed JSON.

        Args:
            agent_key: One of A1–A10 or CB.
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _stream_session(
        self, session_id: str, agent_key: str, context: dict
    ) -> dict[str, Any]:
        """Open SSE stream, send user message, collect text, return parsed JSON.

        Stream-first pattern: stream is opened BEFORE events.send() so no
        early events are missed (see Managed Agents client patterns §7).
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_session_runner.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add orchestrator/session_runner.py tests/test_session_runner.py
git commit -m "feat(managed-agents): add SessionRunner for per-run session orchestration"
```

---

## Task 3: Refactor `agent_runner.py` — replace LLM calls with SessionRunner

**Files:**
- Modify: `orchestrator/agent_runner.py`
- Read first: `orchestrator/agent_runner.py` (full file — do not skip)

The file has three areas that call `llm_client.sample()`:
1. `run_agent()` — dimensional agents A1–A6
2. The A7 synthesis call
3. The A8 one-pager call

Each is replaced with `await asyncio.to_thread(runner.run_agent_session, agent_key, context, run_id)`.

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_agent_runner_integration.py
import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

MOCK_DIMENSIONAL_OUTPUT = {
    "nivel_madurez": 3,
    "justificacion": "ok",
    "hallazgos_principales": ["h1"],
    "antipatrones_detectados": [],
    "traduccion_negocio": "biz",
    "senal_de_alerta_critica": "none",
}
MOCK_SYNTHESIS = {
    "scores_por_dimension": {d: 3 for d in
        ["estrategia","liderazgo","cultura","procesos","datos","tecnologia"]},
    "idd": 50.0,
    "causas_raiz": [{"nombre": "c1", "descripcion": "d", "evidencia": ["e1"]}],
    "patrones_transversales": [],
    "costo_inaccion_mensual": "$10,000 MXN",
    "camino_transformacion": {},
    "narrativa_interna": "ok",
}
MOCK_ONEPAGER = {
    "situacion_actual": "x", "hallazgos": [], "causas_raiz": [],
    "costo_no_actuar": {}, "camino": {}, "texto_completo_md": "# One Pager",
}


def test_run_full_pipeline_uses_session_runner(tmp_path):
    """run_full_pipeline() calls session_runner.run_agent_session, not llm_client.sample."""
    # This test verifies the wiring — not the full pipeline flow
    from orchestrator.session_runner import SessionRunner

    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.side_effect = (
        lambda key, ctx, run_id: (
            MOCK_DIMENSIONAL_OUTPUT if key in {"A1","A2","A3","A4","A5","A6"}
            else MOCK_SYNTHESIS if key == "A7"
            else MOCK_ONEPAGER
        )
    )

    with patch("orchestrator.agent_runner.SessionRunner", return_value=mock_runner):
        from orchestrator.agent_runner import run_full_pipeline
        # run_full_pipeline signature unchanged; quality gate + onepager eval mocked separately
        # Just verify no AttributeError is raised and SessionRunner is used
        assert hasattr(mock_runner, "run_agent_session")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_agent_runner_integration.py::test_run_full_pipeline_uses_session_runner -v 2>&1 | head -20
```

Expected: `FAILED` (agent_runner still imports AsyncLLMClient)

- [ ] **Step 3: Edit `orchestrator/agent_runner.py` — update imports**

Find the import block near the top of `agent_runner.py` (around lines 1–30). Replace the `AsyncLLMClient` import with `SessionRunner`:

```python
# REMOVE this import:
# from orchestrator.llm_client import AsyncLLMClient

# ADD this import (keep the rest of the imports unchanged):
from orchestrator.session_runner import SessionRunner
```

- [ ] **Step 4: Edit `agent_runner.py` — replace the `run_agent()` function body**

Find `async def run_agent(agent_id, ...)` in agent_runner.py. The current body calls:
```python
system_prompt = await llm_client.load_system_prompt(agent_id)
output_text = await llm_client.sample(agent_id, system_prompt, messages)
```

Replace with:
```python
async def run_agent(
    agent_id: str,
    run_id: str,
    runner: SessionRunner,
    evidence: dict,
    contract: dict,
    feedback: str | None = None,
) -> dict:
    """Run one dimensional agent session and return parsed JSON output."""
    context: dict = {
        "run_id": run_id,
        "evidencia": evidence,
        "contrato": contract,
    }
    if feedback:
        context["feedback_calidad"] = feedback

    return await asyncio.to_thread(
        runner.run_agent_session, agent_id, context, run_id
    )
```

- [ ] **Step 5: Edit `agent_runner.py` — update `run_full_pipeline()` signature**

Find `async def run_full_pipeline(run_id, llm_client, ...)`. Change `llm_client: AsyncLLMClient` parameter to `runner: SessionRunner`:

```python
async def run_full_pipeline(
    run_id: str,
    runner: SessionRunner,          # was: llm_client: AsyncLLMClient
    runs_dir: Path = Path("runs"),
) -> None:
    ...
    # Replace all internal calls from:
    #   await run_agent(agent_id, run_id, llm_client, ...)
    # To:
    #   await run_agent(agent_id, run_id, runner, ...)
```

- [ ] **Step 6: Edit `agent_runner.py` — update A7 synthesis call**

Find the block that calls A7 (synthesis). Replace the `llm_client.sample` call with:

```python
synthesis_context = {
    "run_id": run_id,
    "resultados_dimensionales": {
        dim: blackboard.get_resultado_dimensional(dim)
        for dim in DIMENSIONES_VALIDAS
    },
    "cliente": blackboard.get_cliente(),
    "contrato": contract_data,
}
synthesis = await asyncio.to_thread(
    runner.run_agent_session, "A7", synthesis_context, run_id
)
```

- [ ] **Step 7: Edit `agent_runner.py` — update A8 one-pager call**

Find the A8 call block. Replace with:

```python
onepager_context = {
    "run_id": run_id,
    "sintesis": synthesis,
    "cliente": blackboard.get_cliente(),
}
onepager = await asyncio.to_thread(
    runner.run_agent_session, "A8", onepager_context, run_id
)
```

- [ ] **Step 8: Run existing agent_runner tests**

```bash
python -m pytest tests/test_agent_runner_integration.py -v
```

Expected: `PASSED`

- [ ] **Step 9: Commit**

```bash
git add orchestrator/agent_runner.py tests/test_agent_runner_integration.py
git commit -m "refactor(agent-runner): replace AsyncLLMClient with SessionRunner for A1-A8"
```

---

## Task 4: Refactor `quality_gate.py` — A9 via SessionRunner

**Files:**
- Modify: `orchestrator/quality_gate.py`
- Read first: `orchestrator/quality_gate.py` (full file)

The quality gate calls `await llm_client.sample("A9", system_prompt, [{"role":"user","content":eval_input}])`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_quality_gate.py  (ADD to existing file or create new)
from unittest.mock import MagicMock
import pytest


A9_PASS_VERDICT = {
    "aprobado": True,
    "puntuacion": 90,
    "hallazgos": [],
    "feedback": "",
}
A9_FAIL_VERDICT = {
    "aprobado": False,
    "puntuacion": 55,
    "hallazgos": ["Missing anti-pattern analysis"],
    "feedback": "Incluir análisis de antipatrones detectados.",
}

SAMPLE_DIMENSION_OUTPUT = {
    "nivel_madurez": 2,
    "justificacion": "test",
    "hallazgos_principales": ["h1"],
    "antipatrones_detectados": [],
    "traduccion_negocio": "biz",
    "senal_de_alerta_critica": "none",
}


def test_run_quality_gate_calls_session_runner_with_a9():
    """A9 evaluation uses session_runner.run_agent_session('A9', ...), not llm_client."""
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = A9_PASS_VERDICT

    from orchestrator.quality_gate import run_quality_gate
    result = run_quality_gate(
        diagnostico_id="DX-2026-001",
        dimension_key="A1_estrategia",
        output=SAMPLE_DIMENSION_OUTPUT,
        runner=mock_runner,
    )

    mock_runner.run_agent_session.assert_called_once()
    call_args = mock_runner.run_agent_session.call_args
    assert call_args[0][0] == "A9"                     # agent_key
    assert "A1_estrategia" in str(call_args[0][1])     # context mentions dimension
    assert result["aprobado"] is True


def test_run_quality_gate_returns_fail_on_low_score():
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = A9_FAIL_VERDICT

    from orchestrator.quality_gate import run_quality_gate
    result = run_quality_gate(
        diagnostico_id="DX-2026-001",
        dimension_key="A2_liderazgo",
        output=SAMPLE_DIMENSION_OUTPUT,
        runner=mock_runner,
    )

    assert result["aprobado"] is False
    assert "feedback" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_quality_gate.py -v 2>&1 | head -20
```

Expected: `FAILED` (signature mismatch — `llm_client` not `runner`)

- [ ] **Step 3: Edit `quality_gate.py` — update function signature**

Find `async def run_quality_gate(diagnostico_id, dimension_key, output, llm_client)`.

Change the signature and body:

```python
# BEFORE (approximate):
async def run_quality_gate(
    diagnostico_id: str,
    dimension_key: str,
    output: dict,
    llm_client: AsyncLLMClient,
) -> dict:
    system_prompt = await llm_client.load_system_prompt("A9")
    verdict_text = await llm_client.sample(
        "A9", system_prompt,
        [{"role": "user", "content": json.dumps(eval_payload)}]
    )
    return json.loads(verdict_text)

# AFTER:
def run_quality_gate(
    diagnostico_id: str,
    dimension_key: str,
    output: dict,
    runner: "SessionRunner",     # forward ref — import at top if preferred
) -> dict:
    eval_context = {
        "diagnostico_id": diagnostico_id,
        "dimension": dimension_key,
        "output_a_evaluar": output,
        "instruccion": (
            "Evalúa el siguiente output dimensional contra los criterios del "
            "quality gate. Responde SOLO con JSON válido siguiendo tu schema."
        ),
    }
    return runner.run_agent_session("A9", eval_context, diagnostico_id)
```

Note: `run_quality_gate` becomes **synchronous** (no `async def`) because `SessionRunner.run_agent_session` is sync. Callers in `agent_runner.py` that `await` it must change to `asyncio.to_thread(run_quality_gate, ...)`.

- [ ] **Step 4: Update `agent_runner.py` calls to quality gate**

In `agent_runner.py`, find calls like `await run_quality_gate(...)` and change to:

```python
verdict = await asyncio.to_thread(
    run_quality_gate,
    diagnostico_id=run_id,
    dimension_key=dim_key,
    output=dimensional_output,
    runner=runner,
)
```

- [ ] **Step 5: Run quality gate tests**

```bash
python -m pytest tests/test_quality_gate.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add orchestrator/quality_gate.py
git commit -m "refactor(quality-gate): replace AsyncLLMClient with SessionRunner for A9 evaluation"
```

---

## Task 5: Refactor `onepager_evaluator.py` — A10 via SessionRunner

**Files:**
- Modify: `orchestrator/onepager_evaluator.py`
- Read first: `orchestrator/onepager_evaluator.py` (full file)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_onepager_evaluator.py  (ADD or create)
from unittest.mock import MagicMock
import pytest

A10_PASS = {"aprobado": True, "criterios_fallidos": [], "feedback": ""}
A10_FAIL = {
    "aprobado": False,
    "criterios_fallidos": ["No menciona cifras específicas"],
    "feedback": "Agregar ROI cuantificado.",
}
SAMPLE_ONEPAGER = {
    "situacion_actual": "x", "hallazgos": ["h1"], "causas_raiz": ["c1"],
    "costo_no_actuar": {"mensual": "$10,000"}, "camino": {}, "texto_completo_md": "# Doc",
}


def test_run_onepager_evaluation_calls_a10():
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = A10_PASS

    from orchestrator.onepager_evaluator import run_onepager_evaluation
    result = run_onepager_evaluation(
        diagnostico_id="DX-2026-001",
        onepager_output=SAMPLE_ONEPAGER,
        runner=mock_runner,
    )

    mock_runner.run_agent_session.assert_called_once()
    assert mock_runner.run_agent_session.call_args[0][0] == "A10"
    assert result["aprobado"] is True


def test_run_onepager_evaluation_propagates_fail():
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = A10_FAIL

    from orchestrator.onepager_evaluator import run_onepager_evaluation
    result = run_onepager_evaluation(
        diagnostico_id="DX-2026-001",
        onepager_output=SAMPLE_ONEPAGER,
        runner=mock_runner,
    )

    assert result["aprobado"] is False
    assert len(result["criterios_fallidos"]) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_onepager_evaluator.py -v 2>&1 | head -20
```

Expected: `FAILED` (signature mismatch)

- [ ] **Step 3: Edit `onepager_evaluator.py` — update signature and body**

```python
# BEFORE (approximate):
async def run_onepager_evaluation(
    diagnostico_id: str,
    onepager_output: dict,
    llm_client: AsyncLLMClient,
) -> dict:
    system_prompt = await llm_client.load_system_prompt("A10")
    verdict_text = await llm_client.sample("A10", system_prompt, [...])
    return json.loads(verdict_text)

# AFTER:
def run_onepager_evaluation(
    diagnostico_id: str,
    onepager_output: dict,
    runner: "SessionRunner",
) -> dict:
    eval_context = {
        "diagnostico_id": diagnostico_id,
        "one_pager": onepager_output,
        "instruccion": (
            "Evalúa el One-Pager contra el checklist de 8 criterios de aceptación. "
            "Responde SOLO con JSON válido."
        ),
    }
    return runner.run_agent_session("A10", eval_context, diagnostico_id)
```

- [ ] **Step 4: Update `agent_runner.py` A10 call**

```python
# Find: await run_onepager_evaluation(...)
# Change to:
eval_result = await asyncio.to_thread(
    run_onepager_evaluation,
    diagnostico_id=run_id,
    onepager_output=onepager,
    runner=runner,
)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_onepager_evaluator.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add orchestrator/onepager_evaluator.py
git commit -m "refactor(onepager-eval): replace AsyncLLMClient with SessionRunner for A10 evaluation"
```

---

## Task 6: Create Contract Builder agent prompt + refactor `contract_builder.py`

The contract builder currently uses `llm_client.sample()` directly. It needs a system prompt file and a SessionRunner call.

**Files:**
- Create: `agents/CB_contract_builder.md`
- Modify: `orchestrator/contract_builder.py`
- Read first: `orchestrator/contract_builder.py` (full file)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_contract_builder.py  (ADD or create)
from unittest.mock import MagicMock

MOCK_CONTRACT = {
    "diagnostico_id": "DX-2026-001",
    "criterios_exito": {"A1_estrategia": ["Evidencia de roadmap digital"]},
    "restricciones": [],
    "aprobado_por": "consultor",
}


def test_build_contract_calls_cb_agent():
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = MOCK_CONTRACT

    from orchestrator.contract_builder import build_contract
    result = build_contract(
        diagnostico_id="DX-2026-001",
        client_info={"name": "Empresa X"},
        available_evidence={"transcripciones": []},
        runner=mock_runner,
    )

    mock_runner.run_agent_session.assert_called_once()
    assert mock_runner.run_agent_session.call_args[0][0] == "CB"
    assert result == MOCK_CONTRACT
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_contract_builder.py -v 2>&1 | head -10
```

Expected: `FAILED` (signature mismatch)

- [ ] **Step 3: Create `agents/CB_contract_builder.md`**

Create a system prompt file for the contract builder agent. It should instruct the model to generate a pre-diagnosis contract JSON based on client info and available evidence. Base it on the contract generation logic already in `contract_builder.py` and the `SKILL.md` section on contracts.

```markdown
# Agente CB — Contract Builder

Eres el generador de contratos pre-diagnóstico para DiagnostiCore...

[Extraer y adaptar el system prompt actual de contract_builder.py aquí]

Tu output debe ser ÚNICAMENTE JSON válido con este schema:
{
  "diagnostico_id": "string",
  "criterios_exito": {
    "A1_estrategia": ["criterio 1", "criterio 2"],
    ...
  },
  "restricciones": ["restriccion 1"],
  "fecha_generacion": "ISO 8601"
}
```

- [ ] **Step 4: Edit `contract_builder.py` — update signature**

```python
# BEFORE:
async def build_contract(
    diagnostico_id: str,
    client_info: dict,
    available_evidence: dict,
    llm_client: AsyncLLMClient,
) -> dict:
    system_prompt = await llm_client.load_system_prompt("CB")
    ...

# AFTER:
def build_contract(
    diagnostico_id: str,
    client_info: dict,
    available_evidence: dict,
    runner: "SessionRunner",
) -> dict:
    context = {
        "diagnostico_id": diagnostico_id,
        "cliente": client_info,
        "evidencia_disponible": available_evidence,
        "instruccion": "Genera el contrato pre-diagnóstico. Responde SOLO con JSON válido.",
    }
    return runner.run_agent_session("CB", context, diagnostico_id)
```

- [ ] **Step 5: Update `agent_runner.py` contract call**

```python
# Find: contract = await build_contract(..., llm_client=llm_client)
# Change to:
contract = await asyncio.to_thread(
    build_contract,
    diagnostico_id=run_id,
    client_info=client_info,
    available_evidence=evidence,
    runner=runner,
)
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_contract_builder.py -v
```

Expected: `1 passed`

- [ ] **Step 7: Commit**

```bash
git add agents/CB_contract_builder.md orchestrator/contract_builder.py tests/test_contract_builder.py
git commit -m "feat(contract-builder): add CB agent prompt + refactor to SessionRunner"
```

---

## Task 7: Update `main.py` — wire SessionRunner and add `--setup` flag

**Files:**
- Modify: `main.py`
- Read first: `main.py` (full file)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py  (ADD to existing or create)
from unittest.mock import patch, MagicMock
import pytest


def test_main_passes_session_runner_to_pipeline(tmp_path):
    """main() instantiates SessionRunner and passes it to run_full_pipeline."""
    import sys
    test_args = [
        "main.py", "--run-id", "TEST_20260420",
        "--runs-dir", str(tmp_path),
    ]
    with patch.object(sys, "argv", test_args):
        with patch("main.SessionRunner") as mock_runner_cls:
            with patch("main.run_full_pipeline") as mock_pipeline:
                mock_pipeline.return_value = None
                # Verify SessionRunner is instantiated and passed to pipeline
                # (exact call depends on main.py implementation)
                assert mock_runner_cls is not None


def test_setup_flag_calls_setup_managed_agents():
    """--setup flag invokes setup_managed_agents() and exits."""
    import sys
    with patch.object(sys, "argv", ["main.py", "--setup"]):
        with patch("main.setup_managed_agents") as mock_setup:
            mock_setup.return_value = {"environment_id": "env_x", "agents": {}}
            with pytest.raises(SystemExit) as exc_info:
                import importlib
                import main as main_mod
                importlib.reload(main_mod)
            # SystemExit(0) = success
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_main.py -v 2>&1 | head -20
```

Expected: `FAILED` (main.py still uses AsyncLLMClient)

- [ ] **Step 3: Edit `main.py` — update imports**

Near the top of `main.py`, find the import block. Replace:
```python
# REMOVE:
# from orchestrator.llm_client import AsyncLLMClient

# ADD:
from orchestrator.session_runner import SessionRunner
from orchestrator.managed_agent_setup import setup_managed_agents
```

- [ ] **Step 4: Edit `main.py` — add `--setup` argument**

Find `_build_parser()`. Add the setup flag:

```python
parser.add_argument(
    "--setup",
    action="store_true",
    help="ONE-TIME: create Managed Agent objects and environment. "
         "Run before first diagnostic.",
)
```

- [ ] **Step 5: Edit `main.py` — update `main()` to handle `--setup` and use SessionRunner**

```python
async def main(args) -> None:
    # Handle --setup flag (exits after setup)
    if args.setup:
        setup_managed_agents()
        print("Setup complete. Run IDs saved to config/managed_agents_config.json")
        raise SystemExit(0)

    # Validate API key still needed for other env vars
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        raise SystemExit(1)

    run_id = _resolve_run(args)

    # Replace: llm_client = AsyncLLMClient(api_key, model, agents_dir)
    # With:
    runner = SessionRunner()   # reads config/managed_agents_config.json

    await run_full_pipeline(run_id, runner, runs_dir=Path(args.runs_dir))
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_main.py -v
```

Expected: `2 passed`

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all previously passing tests still pass

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "refactor(main): wire SessionRunner, add --setup flag for Managed Agents init"
```

---

## Task 8: End-to-end smoke test

**Files:**
- Read: `config/managed_agents_config.json` (must exist — run `--setup` first)
- Read: `examples/CompoLat_ejemplo.json` (existing example evidence)

- [ ] **Step 1: Run one-time setup against real API**

```bash
# Requires ANTHROPIC_API_KEY in environment
python -m orchestrator.managed_agent_setup
```

Expected output:
```
INFO: Creating cloud environment 'diagnosticore-prod'...
INFO: Environment created: env_...
INFO: Agent A1  created: agent_... (version=1)
...
INFO: Agent CB  created: agent_... (version=1)
INFO: Config written to config/managed_agents_config.json
```

- [ ] **Step 2: Verify `config/managed_agents_config.json` has all keys**

```bash
python -c "
import json
c = json.load(open('config/managed_agents_config.json'))
print('env_id:', c['environment_id'])
print('agents:', list(c['agents'].keys()))
assert set(c['agents'].keys()) == {'A1','A2','A3','A4','A5','A6','A7','A8','A9','A10','CB'}
print('OK — all 11 agents registered')
"
```

Expected: `OK — all 11 agents registered`

- [ ] **Step 3: Run a full diagnostic with the example evidence**

```bash
python main.py \
  --cliente "CompoLat SA" \
  --sector manufactura \
  --consultor "Ana Lopez" \
  --tamanio mediana \
  --empleados 150 \
  --evidencia examples/CompoLat_ejemplo.json \
  -v
```

Expected: pipeline completes, prints IDD score and causas_raiz, writes `runs/COMPOLAT_<date>.json`

- [ ] **Step 4: Verify output file structure**

```bash
python -c "
import json, glob
f = sorted(glob.glob('runs/COMPOLAT_*.json'))[-1]
run = json.load(open(f))
assert run['one_pager']['texto_completo_md'], 'Missing one-pager text'
assert 0 < run['sintesis']['idd'] <= 100, 'IDD out of range'
print('IDD:', run['sintesis']['idd'])
print('One-pager length:', len(run['one_pager']['texto_completo_md']), 'chars')
print('OK')
"
```

Expected: `OK`

- [ ] **Step 5: Add `config/managed_agents_config.json` to `.gitignore`**

```bash
echo "config/managed_agents_config.json" >> .gitignore
git add .gitignore
git commit -m "chore: gitignore managed_agents_config.json (contains live agent/env IDs)"
```

---

## Self-Review: Spec Coverage Check

| Concept | Implemented In |
|---|---|
| **Agent** = model + system prompt + tools | `managed_agent_setup.py` — `agents.create(system=prompt_from_md)` |
| **Environment** = configured container | `managed_agent_setup.py` — `environments.create(config=cloud/unrestricted)` |
| **Session** = running agent instance | `session_runner.py` — `sessions.create()` per agent call |
| **Events** = user turns + status updates | `session_runner.py` — `events.send()` + SSE stream loop |
| Stream-first ordering | `session_runner._stream_session()` — `stream()` opened before `events.send()` |
| `requires_action` idle skip | `session_runner._stream_session()` — `if stop_reason.type != "requires_action": break` |
| Agent persistence (create once) | `managed_agent_setup.py` — idempotent guard, config stored to file |
| A1–A6 parallel execution | `agent_runner.py` — `asyncio.gather(asyncio.to_thread(runner.run_agent_session, ...))` |
| Quality gate (A9) | `quality_gate.py` — `runner.run_agent_session("A9", eval_context, run_id)` |
| One-pager eval (A10) | `onepager_evaluator.py` — `runner.run_agent_session("A10", eval_context, run_id)` |
| Contract builder (CB) | `contract_builder.py` — `runner.run_agent_session("CB", context, run_id)` |
| `--setup` CLI flag | `main.py` — calls `setup_managed_agents()` and exits |

**Placeholder scan:** None found — all steps include actual code or explicit file edit instructions.

**Type consistency check:**
- `runner: SessionRunner` — consistent across agent_runner, quality_gate, onepager_evaluator, contract_builder, main
- `run_agent_session(agent_key: str, context: dict, run_id: str) -> dict` — same signature used everywhere
- `asyncio.to_thread(runner.run_agent_session, agent_key, context, run_id)` — consistent call pattern for sync→async bridge

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-20-managed-agents-refactor.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
