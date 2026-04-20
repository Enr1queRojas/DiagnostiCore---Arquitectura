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
    """session.status_terminated stops the loop; no output → LLMError."""
    from orchestrator.exceptions import LLMError
    mock_client = MagicMock()
    mock_client.beta.sessions.create.return_value = MagicMock(id="sesn_002")
    mock_client.beta.sessions.stream.return_value = _mock_stream([
        _make_terminated_event(),
    ])

    runner = _build_runner(mock_client)
    with pytest.raises(LLMError, match="no output"):
        runner.run_agent_session("A1", {}, "RUN")


def test_run_agent_session_skips_requires_action_idle():
    """requires_action idle does NOT break the loop; subsequent end_turn idle does."""
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
