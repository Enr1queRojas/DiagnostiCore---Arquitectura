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
