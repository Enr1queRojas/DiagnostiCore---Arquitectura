"""
orchestrator/exceptions.py
===========================
Custom exception hierarchy for the DiagnostiCore execution engine.

All public exceptions inherit from DiagnostiCoreError so callers can
catch the entire domain with a single except clause when needed, while
still distinguishing root causes when precision matters.
"""


class DiagnostiCoreError(Exception):
    """
    Base class for all DiagnostiCore runtime errors.
    Catching this type covers the entire domain exception tree.
    """


# ─────────────────────────────────────────────────────────────────────────────
# LLM-layer exceptions
# ─────────────────────────────────────────────────────────────────────────────

class LLMError(DiagnostiCoreError):
    """
    Raised when the Anthropic API call fails or returns an unrecoverable
    transport-level error (connection refused, auth failure, persistent
    rate-limit after all retries, etc.).

    Attributes:
        agent_id:  The agent that triggered the call (empty string if unknown).
        attempt:   How many attempts were made before giving up (0 = not tried).
    """

    def __init__(self, message: str, agent_id: str = "", attempt: int = 0):
        self.agent_id = agent_id
        self.attempt = attempt
        super().__init__(message)


class AgentOutputError(LLMError):
    """
    Raised when the LLM *responds* successfully but the response cannot be
    parsed as JSON or coerced into a valid structure even after the
    self-correction retry.

    This is a sub-class of LLMError because the root cause is still the
    LLM interaction, not a schema rule violation.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Validation-layer exceptions
# ─────────────────────────────────────────────────────────────────────────────

class ValidationError(DiagnostiCoreError):
    """
    Raised when parsed agent output violates the JSON Schema or a
    DiagnostiCore business rule (e.g. > 3 causas_raiz, invalid antipattern ID).

    Attributes:
        agent_id:          The agent whose output was being validated.
        validation_errors: List of human-readable error messages from jsonschema.
    """

    def __init__(
        self,
        message: str,
        agent_id: str = "",
        errors: list[str] | None = None,
    ):
        self.agent_id = agent_id
        self.validation_errors: list[str] = errors or []
        super().__init__(message)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline-layer exceptions
# ─────────────────────────────────────────────────────────────────────────────

class OrchestratorError(DiagnostiCoreError):
    """
    Raised for pipeline-level failures: state transition errors, the
    blackboard rejecting a write, or a phase completing with one or more
    agent failures.

    Attributes:
        failed_agents: IDs of the agents that did not complete successfully.
    """

    def __init__(self, message: str, failed_agents: list[str] | None = None):
        self.failed_agents: list[str] = failed_agents or []
        super().__init__(message)
