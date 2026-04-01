"""
mcp_adapter/pii_filter.py
==========================
PII anonymization layer for DiagnostiCore.

All evidence text passes through this module BEFORE reaching the LLM to ensure
no Personally Identifiable Information leaves the consultant's environment.

Patterns target the Mexican administrative and business context:
  - RFC  (Registro Federal de Contribuyentes)  — 12-13 alphanumeric chars
  - CURP (Clave Única de Registro de Población) — 18 alphanumeric chars
  - IMSS / NSS (Número de Seguridad Social)     — 11 digits
  - Phone numbers in Mexican formats (10 digits, with +52 prefix, etc.)
  - Full names via a heuristic two-or-more consecutive Title Case words
  - Email addresses
  - Full numeric dates (DD/MM/YYYY and YYYY-MM-DD)

Design decisions:
  - Returns a FilterResult dataclass so callers can log how many replacements
    were made without needing to parse the transformed text.
  - Substitution tokens are bracketed (e.g. [RFC_REDACTED]) so the LLM can
    infer what kind of data was present without seeing the actual value.
  - Patterns are pre-compiled once at module load for performance.
  - Filter is idempotent: running it twice produces the same output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

# ─────────────────────────────────────────────────────────────────────────────
# Compiled PII patterns
# ─────────────────────────────────────────────────────────────────────────────

# RFC — 12 chars for moral persons, 13 for natural persons.
# Pattern: 3-4 letters + 6-digit date + 2-3 alphanumeric homoclave.
_PAT_RFC: Final = re.compile(
    r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3}\b",
    re.IGNORECASE,
)

# CURP — exactly 18 alphanumeric characters in a rigid structure.
_PAT_CURP: Final = re.compile(
    r"\b[A-Z]{1}[AEIOU]{1}[A-Z]{2}\d{6}[HM]{1}[A-Z]{2}[A-Z0-9]{3}[A-Z0-9]{1}\d{1}\b",
    re.IGNORECASE,
)

# NSS (IMSS) — 11 consecutive digits.
_PAT_NSS: Final = re.compile(r"\b\d{11}\b")

# Mexican phone numbers:
#   +52 1 XXX XXX XXXX  — mobile with country code
#   +52 XXX XXX XXXX    — landline with country code
#   (55) XXXX XXXX      — area code in parens
#   55 1234 5678        — bare 10-digit
_PAT_PHONE: Final = re.compile(
    r"(?:\+52[\s\-.]?1?[\s\-.]?)?(?:\(?\d{2,3}\)?[\s\-.]?)?\d{4}[\s\-.]?\d{4}",
    re.IGNORECASE,
)

# Email addresses.
_PAT_EMAIL: Final = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

# Full dates: 01/12/2025, 2025-12-01, 01-12-2025
_PAT_DATE: Final = re.compile(
    r"\b(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})\b"
)

# Proper names heuristic: two or more consecutive Title Case words.
# Excludes all-caps acronyms and common Spanish prepositions.
_EXCLUDED_WORDS: Final = frozenset({
    "El", "La", "Los", "Las", "De", "Del", "En", "Con", "Por",
    "Para", "Sin", "Sobre", "A", "Y", "E", "O", "U", "Pero",
    "Empresa", "Director", "Gerente", "Área", "Departamento",
})

_PAT_PROPER_NAME: Final = re.compile(
    r"\b(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})(?:\s+(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})){1,4}\b"
)


def _is_excluded(match_text: str) -> bool:
    """Return True if the matched text is a known non-name phrase."""
    words = match_text.split()
    # If all words are in the exclusion list, skip
    return all(w in _EXCLUDED_WORDS for w in words)


# ─────────────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FilterResult:
    """
    Outcome of a PII filtering pass.

    Attributes:
        text:           The anonymized output text.
        replacements:   Dict mapping replacement token → count of substitutions.
        total_replaced: Total number of PII instances removed.
    """
    text: str
    replacements: dict[str, int] = field(default_factory=dict)
    total_replaced: int = 0

    def __bool__(self) -> bool:
        """True if any PII was found and removed."""
        return self.total_replaced > 0


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def filter_pii(text: str, *, redact_names: bool = True) -> FilterResult:
    """
    Anonymize all detected PII in *text*.

    Args:
        text:          Raw evidence text (transcriptions, survey answers, notes).
        redact_names:  Whether to apply the proper-name heuristic.
                       Defaults to True. Set to False for structured data
                       (JSON scores, numbers) where the heuristic may cause
                       false positives.

    Returns:
        FilterResult with the anonymized text and replacement counts.
    """
    replacements: dict[str, int] = {}
    output = text

    def _replace(pattern: re.Pattern, token: str, haystack: str) -> tuple[str, int]:
        count = 0
        def _sub(m: re.Match) -> str:  # noqa: ANN001
            nonlocal count
            count += 1
            return token
        result = pattern.sub(_sub, haystack)
        return result, count

    # Apply patterns in priority order (most specific first)
    for pat, token in [
        (_PAT_CURP,   "[CURP_REDACTED]"),
        (_PAT_RFC,    "[RFC_REDACTED]"),
        (_PAT_NSS,    "[NSS_REDACTED]"),
        (_PAT_EMAIL,  "[EMAIL_REDACTED]"),
        (_PAT_PHONE,  "[PHONE_REDACTED]"),
        (_PAT_DATE,   "[DATE_REDACTED]"),
    ]:
        output, n = _replace(pat, token, output)
        if n:
            replacements[token] = replacements.get(token, 0) + n

    # Proper name heuristic (optional, can produce false positives on brand names)
    if redact_names:
        name_count = 0

        def _sub_name(m: re.Match) -> str:  # noqa: ANN001
            nonlocal name_count
            if _is_excluded(m.group(0)):
                return m.group(0)  # Leave exclusion-list phrases as-is
            name_count += 1
            return "[NOMBRE_REDACTED]"

        output = _PAT_PROPER_NAME.sub(_sub_name, output)
        if name_count:
            replacements["[NOMBRE_REDACTED]"] = name_count

    total = sum(replacements.values())
    return FilterResult(text=output, replacements=replacements, total_replaced=total)


def filter_evidence_dict(evidencia: dict) -> tuple[dict, FilterResult]:
    """
    Apply PII filtering to the evidence block exported from the Blackboard.

    Only the 'texto' field of each transcription is filtered; structured
    metadata (roles, dates already redacted) is left untouched.

    Args:
        evidencia: The dict from blackboard.exportar_para_agente()['evidencia'].

    Returns:
        (filtered_evidencia, combined_result) — the anonymized dict and a
        FilterResult aggregating all substitutions across all transcriptions.
    """
    import copy
    evidencia_copy = copy.deepcopy(evidencia)
    combined_replacements: dict[str, int] = {}
    combined_total = 0

    for tx in evidencia_copy.get("transcripciones", []):
        if "texto" in tx and isinstance(tx["texto"], str):
            result = filter_pii(tx["texto"])
            tx["texto"] = result.text
            for token, count in result.replacements.items():
                combined_replacements[token] = combined_replacements.get(token, 0) + count
            combined_total += result.total_replaced

    return evidencia_copy, FilterResult(
        text="[multiple transcriptions]",
        replacements=combined_replacements,
        total_replaced=combined_total,
    )
