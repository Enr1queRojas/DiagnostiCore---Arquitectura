"""
orchestrator
============
DiagnostiCore execution engine.

Public surface:
  • run_full_pipeline    — run the complete diagnostic pipeline (A1–A11)
  • run_agent            — run a single agent (useful for partial re-runs)
  • OllamaSessionRunner  — local Ollama model driver (default)
  • SessionRunner        — Anthropic Managed Agents driver (cloud)
  • setup_managed_agents — one-time Managed Agent environment initialisation
  • DiagnostiCoreError and subclasses — exception hierarchy
"""

from orchestrator.agent_runner import run_agent, run_full_pipeline
from orchestrator.exceptions import (
    AgentOutputError,
    DiagnostiCoreError,
    LLMError,
    OrchestratorError,
    ValidationError,
)
from orchestrator.ollama_runner import OllamaSessionRunner
from orchestrator.session_runner import SessionRunner
from orchestrator.managed_agent_setup import setup_managed_agents

__all__ = [
    "run_agent",
    "run_full_pipeline",
    "OllamaSessionRunner",
    "SessionRunner",
    "setup_managed_agents",
    "DiagnostiCoreError",
    "LLMError",
    "AgentOutputError",
    "ValidationError",
    "OrchestratorError",
]
