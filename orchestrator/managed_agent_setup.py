# orchestrator/managed_agent_setup.py
"""ONE-TIME setup: create 1 cloud environment + 11 Managed Agent objects (A1-A10 + CB).

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
    "CB":  "CB_contract_builder.md",
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
        # Prefer the canonical filename from the map; fall back to {key}.md for
        # environments where only the short form is present (e.g. test stubs).
        prompt_path = agents_dir / prompt_file
        if not prompt_path.exists():
            prompt_path = agents_dir / f"{agent_key}.md"
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
