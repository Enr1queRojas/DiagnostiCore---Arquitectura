"""
auth — JWT-based run isolation for DiagnostiCore.

Ensures that each consultant can only access and modify the run(s)
they created — critical for multi-consultant deployments.
"""

from auth.jwt_auth import (
    RunTokenClaims,
    TokenExpiredError,
    TokenInvalidError,
    TokenRunMismatchError,
    create_run_token,
    verify_run_token,
)

__all__ = [
    "create_run_token",
    "verify_run_token",
    "RunTokenClaims",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenRunMismatchError",
]
