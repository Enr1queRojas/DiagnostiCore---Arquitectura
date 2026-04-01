"""
api/models.py
==============
Pydantic request and response models for the DiagnostiCore REST API.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────

class RunCreateRequest(BaseModel):
    """Body for POST /api/runs — creates a new diagnostic run."""
    cliente: str = Field(..., min_length=1, max_length=120, description="Client company name.")
    sector: str = Field(
        default="servicios",
        description="Industry sector.",
        pattern=r"^(manufactura|inmobiliario|comercializadora|servicios|tecnologia|salud|otro)$",
    )
    consultor: str = Field(
        default="Consultor InnoVerse",
        max_length=80,
        description="Responsible consultant name or ID.",
    )
    tamanio: str = Field(
        default="mediana",
        pattern=r"^(micro|pequeña|mediana|grande)$",
        description="Company size bucket.",
    )
    empleados: int = Field(default=0, ge=0, description="Approximate headcount.")
    token_ttl_hours: int = Field(
        default=8,
        ge=1,
        le=72,
        description="JWT token lifetime in hours.",
    )


class PipelineStartRequest(BaseModel):
    """Body for POST /api/runs/{run_id}/pipeline — triggers pipeline execution."""
    model: str = Field(
        default="claude-sonnet-4-6",
        description="Anthropic model ID to use.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────

class RunCreateResponse(BaseModel):
    """Returned by POST /api/runs."""
    run_id: str
    token: str = Field(description="Bearer token — supply via Authorization header to access this run.")
    created_at: str = Field(description="ISO-8601 UTC creation timestamp.")
    token_expires_at: str = Field(description="ISO-8601 UTC token expiry.")


class AgentStatus(BaseModel):
    """Status of a single agent within a run."""
    agent_id: str
    completed: bool
    nivel_madurez: int | None = None
    timestamp: str | None = None


class RunStatusResponse(BaseModel):
    """Returned by GET /api/runs/{run_id}."""
    run_id: str
    estado: str
    cliente: dict[str, Any]
    agentes_completados: list[str]
    agents: list[AgentStatus]
    errores: list[dict[str, Any]]
    idd: float | None = None


class PipelineStartResponse(BaseModel):
    """Returned by POST /api/runs/{run_id}/pipeline."""
    run_id: str
    status: str = "started"
    message: str


class ReportResponse(BaseModel):
    """Returned by GET /api/runs/{run_id}/report."""
    run_id: str
    markdown_summary: str
    idd: float | None = None
    idd_clasificacion: str | None = None
    causas_raiz_count: int = 0
    one_pager_available: bool = False


class ErrorResponse(BaseModel):
    """Standard error envelope."""
    error: str
    detail: str | None = None
