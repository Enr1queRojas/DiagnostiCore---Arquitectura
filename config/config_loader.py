"""
config/config_loader.py
========================
Single source of truth for all configuration loading in DiagnostiCore.

Replaces the scattered JSON loaders spread across quality_gate.py,
agent_runner.py, blackboard.py, and contract_builder.py.

Public API:
    load_antipattern_ids()                  -> frozenset[str]
    load_antipatterns_for_dimension(dim)    -> list[dict]
    load_antipatterns_summary()             -> list[dict]
    load_maturity_scales()                  -> dict
    load_maturity_scale_for_dimension(dim)  -> dict
    load_acceptance_criteria()              -> dict
    load_pesos_idd()                        -> dict
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
# Internal loaders (cached)
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_antipatterns_raw() -> dict:
    path = _CONFIG_DIR / "antipatterns.json"
    if not path.exists():
        logger.warning("antipatterns.json not found at %s", path)
        return {"ids_validos": [], "antipatrones": []}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _load_maturity_scales_raw() -> dict:
    path = _CONFIG_DIR / "maturity_scales.json"
    if not path.exists():
        logger.warning("maturity_scales.json not found at %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _load_acceptance_criteria_raw() -> dict:
    path = _CONFIG_DIR / "acceptance_criteria.json"
    if not path.exists():
        logger.warning("acceptance_criteria.json not found at %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _load_pesos_idd_raw() -> dict:
    path = _CONFIG_DIR / "pesos_idd.json"
    if not path.exists():
        logger.warning("pesos_idd.json not found at %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def load_antipattern_ids() -> frozenset[str]:
    """Return the canonical set of valid antipattern IDs from antipatterns.json."""
    data = _load_antipatterns_raw()
    ids = data.get("ids_validos", [])
    if not ids:
        # Fallback: derive from the antipatrones array
        ids = [ap["id"] for ap in data.get("antipatrones", []) if "id" in ap]
        logger.warning("ids_validos missing from antipatterns.json — derived %d IDs from catalog", len(ids))
    return frozenset(ids)


def load_antipatterns_for_dimension(dimension_key: str) -> list[dict]:
    """Return anti-patterns relevant to the given dimension key."""
    data = _load_antipatterns_raw()
    all_ap: list[dict] = data.get("antipatrones", [])
    return [
        ap for ap in all_ap
        if dimension_key in ap.get("dimensiones", [ap.get("dimension_primaria", "")])
    ]


def load_antipatterns_summary() -> list[dict]:
    """Return simplified anti-pattern list suitable for contract builder prompts."""
    data = _load_antipatterns_raw()
    return [
        {
            "id": ap["id"],
            "nombre": ap["nombre"],
            "prevalencia_pct": ap.get("prevalencia_pct", 0),
            "dimension_primaria": ap.get("dimension_primaria", ""),
            "dimensiones": ap.get("dimensiones", []),
        }
        for ap in data.get("antipatrones", [])
    ]


def load_maturity_scales() -> dict:
    """Return the full maturity scales dict."""
    return _load_maturity_scales_raw()


def load_maturity_scale_for_dimension(dimension_key: str) -> dict:
    """Return maturity scale for a specific dimension, falling back to global."""
    scales = _load_maturity_scales_raw()
    return scales.get(dimension_key, scales.get("global", {}))


def load_acceptance_criteria() -> dict:
    """Return One-Pager acceptance criteria (8 checklist items)."""
    return _load_acceptance_criteria_raw()


def load_pesos_idd() -> dict:
    """Return IDD dimension weights."""
    return _load_pesos_idd_raw()


def invalidate_cache() -> None:
    """Clear all cached config data. Useful in tests that modify config files."""
    _load_antipatterns_raw.cache_clear()
    _load_maturity_scales_raw.cache_clear()
    _load_acceptance_criteria_raw.cache_clear()
    _load_pesos_idd_raw.cache_clear()
