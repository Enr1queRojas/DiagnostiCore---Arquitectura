"""
orchestrator
============
DiagnostiCore execution engine.

Public surface:
  • run_full_pipeline  — run the complete A1-A8 diagnostic sequence
  • run_agent          — run a single agent (useful for partial re-runs)
  • SessionRunner      — per-run Managed Agent session driver
  • setup_managed_agents — one-time Managed Agent environment initialisation
  • AsyncLLMClient     — Anthropic SDK wrapper (kept for backward compatibility)
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
from orchestrator.llm_client import AsyncLLMClient
from orchestrator.session_runner import SessionRunner
from orchestrator.managed_agent_setup import setup_managed_agents

__all__ = [
    "run_agent",
    "run_full_pipeline",
    "SessionRunner",
    "setup_managed_agents",
    "AsyncLLMClient",
    "DiagnostiCoreError",
    "LLMError",
    "AgentOutputError",
    "ValidationError",
    "OrchestratorError",
]
