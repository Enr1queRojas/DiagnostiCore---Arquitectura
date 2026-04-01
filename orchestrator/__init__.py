"""
orchestrator
============
DiagnostiCore execution engine.

Public surface:
  • run_full_pipeline  — run the complete A1-A8 diagnostic sequence
  • run_agent          — run a single agent (useful for partial re-runs)
  • AsyncLLMClient     — Anthropic SDK wrapper
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

__all__ = [
    "run_agent",
    "run_full_pipeline",
    "AsyncLLMClient",
    "DiagnostiCoreError",
    "LLMError",
    "AgentOutputError",
    "ValidationError",
    "OrchestratorError",
]
