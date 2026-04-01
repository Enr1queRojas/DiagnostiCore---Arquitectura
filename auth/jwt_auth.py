"""
auth/jwt_auth.py
=================
JWT-based run-scoped access tokens for DiagnostiCore.

Each diagnostic run is protected by a short-lived Bearer token that binds:
  - run_id   — the specific run this token authorises
  - consultor_id — the consultant who created the run

Tokens are validated before any write operations in multi-consultant
deployments. In single-consultant mode (default), token verification is
optional but the generation step still provides an audit trail.

Secret key:
  Read from the environment variable DIAGNOSTICORE_JWT_SECRET.
  If absent, a static development secret is used and a warning is emitted.
  PRODUCTION DEPLOYMENTS MUST set DIAGNOSTICORE_JWT_SECRET.

Algorithm: HS256 (HMAC-SHA256) — symmetric, sufficient for single-server.
For multi-server deployments, upgrade to RS256 and pass the public key to
verifiers (the verify_run_token function accepts a custom key parameter).

Dependencies:
  PyJWT>=2.8.0  (install via requirements.txt)

Usage:
  token = create_run_token("EMPRESAABC_20260330", "ana.lopez")
  claims = verify_run_token(token, expected_run_id="EMPRESAABC_20260330")
  print(claims.consultor_id)   # "ana.lopez"
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

import jwt

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_ENV_SECRET_KEY: Final[str] = "DIAGNOSTICORE_JWT_SECRET"
_DEV_FALLBACK_SECRET: Final[str] = "diagnosticore-dev-secret-DO-NOT-USE-IN-PRODUCTION"

_ALGORITHM: Final[str] = "HS256"

# Token lifetime — 8 working hours; tune per deployment security policy.
DEFAULT_TTL_HOURS: Final[int] = 8

# JWT claim names
_CLAIM_RUN_ID: Final[str] = "run_id"
_CLAIM_CONSULTOR: Final[str] = "consultor_id"
_ISSUER: Final[str] = "diagnosticore"


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class TokenError(Exception):
    """Base class for all JWT token errors in DiagnostiCore."""


class TokenExpiredError(TokenError):
    """The token is valid but has passed its expiry time."""
    def __init__(self, run_id: str, expired_at: datetime) -> None:
        super().__init__(
            f"Token for run '{run_id}' expired at {expired_at.isoformat()}. "
            f"Generate a new token with: diagnosticore token --run-id {run_id}"
        )
        self.run_id = run_id
        self.expired_at = expired_at


class TokenInvalidError(TokenError):
    """The token is malformed, has an invalid signature, or is missing claims."""
    def __init__(self, detail: str) -> None:
        super().__init__(f"Invalid token: {detail}")


class TokenRunMismatchError(TokenError):
    """The token is valid but authorises a different run_id than expected."""
    def __init__(self, token_run_id: str, expected_run_id: str) -> None:
        super().__init__(
            f"Token authorises run '{token_run_id}' but operation targets "
            f"run '{expected_run_id}'. Tokens are run-scoped — use the token "
            f"generated when this run was created."
        )
        self.token_run_id = token_run_id
        self.expected_run_id = expected_run_id


# ─────────────────────────────────────────────────────────────────────────────
# Claims dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RunTokenClaims:
    """
    Decoded and verified claims from a DiagnostiCore run token.

    All fields are guaranteed valid after verify_run_token() returns.
    """
    run_id: str
    consultor_id: str
    issued_at: datetime
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.now(tz=timezone.utc) > self.expires_at

    def __str__(self) -> str:
        return (
            f"RunToken(run={self.run_id!r}, consultor={self.consultor_id!r}, "
            f"expires={self.expires_at.strftime('%Y-%m-%d %H:%M')} UTC)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Secret key management
# ─────────────────────────────────────────────────────────────────────────────

def _get_secret() -> str:
    """
    Return the JWT signing secret from the environment.

    Falls back to a static development secret with a loud warning.
    The fallback secret is intentionally public — it must never be used
    in production.
    """
    secret = os.environ.get(_ENV_SECRET_KEY, "").strip()
    if secret:
        return secret

    logger.warning(
        "SECURITY WARNING: %s is not set. "
        "Using the insecure development fallback secret. "
        "Set %s in production to a cryptographically strong random value: "
        "python -c \"import secrets; print(secrets.token_hex(32))\"",
        _ENV_SECRET_KEY, _ENV_SECRET_KEY,
    )
    return _DEV_FALLBACK_SECRET


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def create_run_token(
    run_id: str,
    consultor_id: str,
    ttl_hours: int = DEFAULT_TTL_HOURS,
    *,
    secret: str | None = None,
) -> str:
    """
    Generate a signed JWT token that authorises access to *run_id*.

    Args:
        run_id:       The diagnostic run this token will authorise.
        consultor_id: Identifier for the consultant (email, username, etc.).
        ttl_hours:    Token lifetime in hours (default: 8).
        secret:       Override the signing secret (testing only).

    Returns:
        Signed JWT string (Bearer token format).
    """
    if not run_id:
        raise ValueError("run_id cannot be empty")
    if not consultor_id:
        raise ValueError("consultor_id cannot be empty")

    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(hours=ttl_hours)

    payload = {
        "iss": _ISSUER,
        "sub": run_id,             # Standard "subject" claim = run being accessed
        _CLAIM_RUN_ID: run_id,     # Explicit run_id for clarity (redundant with sub)
        _CLAIM_CONSULTOR: consultor_id,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(
        payload,
        secret or _get_secret(),
        algorithm=_ALGORITHM,
    )

    logger.info(
        "Token created | run=%s | consultor=%s | expires=%s",
        run_id, consultor_id, expires_at.strftime("%Y-%m-%d %H:%M UTC"),
    )

    return token


def verify_run_token(
    token: str,
    expected_run_id: str | None = None,
    *,
    secret: str | None = None,
) -> RunTokenClaims:
    """
    Decode, verify, and optionally scope-check a run token.

    Args:
        token:           JWT Bearer token string.
        expected_run_id: If provided, raises TokenRunMismatchError if the token
                         authorises a different run. Pass None to skip the check
                         (e.g., for listing which run a token belongs to).
        secret:          Override the verification secret (testing only).

    Returns:
        RunTokenClaims with all fields validated.

    Raises:
        TokenExpiredError:      Token signature is valid but time has passed exp.
        TokenInvalidError:      Signature invalid, malformed, or missing claims.
        TokenRunMismatchError:  Token is for a different run than expected.
    """
    try:
        payload = jwt.decode(
            token,
            secret or _get_secret(),
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        # Re-raise with a more actionable error message
        try:
            # Decode without verification to extract run_id for the error message
            unverified = jwt.decode(token, options={"verify_signature": False})
            run_id = unverified.get(_CLAIM_RUN_ID, unverified.get("sub", "unknown"))
            exp_ts = unverified.get("exp", 0)
            expired_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
        except Exception:
            run_id = "unknown"
            expired_at = datetime.now(tz=timezone.utc)
        raise TokenExpiredError(run_id, expired_at)

    except jwt.InvalidSignatureError:
        raise TokenInvalidError("Signature verification failed. Token may have been tampered with.")
    except jwt.DecodeError as exc:
        raise TokenInvalidError(f"Cannot decode token: {exc}")
    except jwt.MissingRequiredClaimError as exc:
        raise TokenInvalidError(f"Required claim missing: {exc}")
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError(str(exc))

    # Extract and validate required custom claims
    token_run_id: str = payload.get(_CLAIM_RUN_ID) or payload.get("sub", "")
    consultor_id: str = payload.get(_CLAIM_CONSULTOR, "")

    if not token_run_id:
        raise TokenInvalidError(f"Token is missing the '{_CLAIM_RUN_ID}' claim.")

    # Scope check: token must be for the run being accessed
    if expected_run_id and token_run_id != expected_run_id:
        raise TokenRunMismatchError(token_run_id, expected_run_id)

    # Convert timestamps
    iat_ts: int = payload["iat"]
    exp_ts: int = payload["exp"]

    claims = RunTokenClaims(
        run_id=token_run_id,
        consultor_id=consultor_id,
        issued_at=datetime.fromtimestamp(iat_ts, tz=timezone.utc),
        expires_at=datetime.fromtimestamp(exp_ts, tz=timezone.utc),
    )

    logger.debug("Token verified: %s", claims)
    return claims
