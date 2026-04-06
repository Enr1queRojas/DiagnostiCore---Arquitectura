"""
tests/test_state_manager.py
============================
Unit tests for orchestrator/state_manager.py

Run with:
    pytest tests/test_state_manager.py -v
"""

import json
import sys
from pathlib import Path

import importlib.util

import pytest

# Import state_manager directly (bypasses orchestrator/__init__.py which
# triggers heavy API imports not needed for unit tests)
_ROOT = Path(__file__).parent.parent
_SM_PATH = _ROOT / "orchestrator" / "state_manager.py"
_spec = importlib.util.spec_from_file_location("state_manager", _SM_PATH)
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_state_file(tmp_path, monkeypatch):
    """Redirect the state file to a temp dir for every test."""
    fake_state = tmp_path / "diagnostico-state.json"
    monkeypatch.setattr(sm, "_STATE_FILE", fake_state)
    yield fake_state


# ─────────────────────────────────────────────────────────────────────────────
# Tests: init_state
# ─────────────────────────────────────────────────────────────────────────────

class TestInitState:
    def test_creates_file(self, patch_state_file):
        sm.init_state("DX-2026-001", {"name": "Acme", "industry": "manufactura", "size": "mediana"})
        assert patch_state_file.exists()

    def test_returns_correct_id(self):
        state = sm.init_state("DX-2026-001")
        assert state["diagnostico_id"] == "DX-2026-001"

    def test_initial_status_is_initialized(self):
        state = sm.init_state("DX-2026-001")
        assert state["status"] == "initialized"

    def test_all_dimensions_start_pending(self):
        state = sm.init_state("DX-2026-001")
        for key in sm.DIMENSION_KEYS:
            assert state["dimensions"][key]["status"] == "pending"

    def test_client_fields_stored(self):
        state = sm.init_state(
            "DX-2026-001",
            {"name": "TechCo", "industry": "servicios", "size": "grande"},
        )
        assert state["client"]["name"] == "TechCo"
        assert state["client"]["industry"] == "servicios"

    def test_overwrites_existing_state(self):
        sm.init_state("DX-2026-001")
        sm.init_state("DX-2026-002")
        loaded = sm.load_state("DX-2026-002")
        assert loaded["diagnostico_id"] == "DX-2026-002"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: load_state
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadState:
    def test_raises_if_no_file(self):
        with pytest.raises(FileNotFoundError):
            sm.load_state("DX-2026-999")

    def test_raises_on_id_mismatch(self):
        sm.init_state("DX-2026-001")
        with pytest.raises(ValueError, match="diagnostico_id"):
            sm.load_state("DX-2026-WRONG")

    def test_returns_state_dict(self):
        sm.init_state("DX-2026-001")
        state = sm.load_state("DX-2026-001")
        assert isinstance(state, dict)
        assert state["diagnostico_id"] == "DX-2026-001"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: update_dimension
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateDimension:
    def setup_method(self):
        sm.init_state("DX-2026-001")

    def test_update_status(self):
        sm.update_dimension("DX-2026-001", "A1_estrategia", {"status": "complete"})
        state = sm.load_state("DX-2026-001")
        assert state["dimensions"]["A1_estrategia"]["status"] == "complete"

    def test_update_score_and_eval(self):
        sm.update_dimension(
            "DX-2026-001",
            "A3_cultura",
            {"score": 3, "eval_passed": True, "status": "evaluated"},
        )
        state = sm.load_state("DX-2026-001")
        dim = state["dimensions"]["A3_cultura"]
        assert dim["score"] == 3
        assert dim["eval_passed"] is True
        assert dim["status"] == "evaluated"

    def test_raises_on_invalid_key(self):
        with pytest.raises(ValueError, match="Unknown dimension_key"):
            sm.update_dimension("DX-2026-001", "A99_fake", {"status": "complete"})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: append_history
# ─────────────────────────────────────────────────────────────────────────────

class TestAppendHistory:
    def test_appends_entries(self):
        sm.init_state("DX-2026-001")
        sm.append_history("DX-2026-001", "A1", "complete", "nivel=2")
        sm.append_history("DX-2026-001", "A9", "eval_pass", "all criteria ≥ 3")
        state = sm.load_state("DX-2026-001")
        assert len(state["history"]) == 2
        assert state["history"][0]["agent"] == "A1"
        assert state["history"][1]["agent"] == "A9"

    def test_history_has_timestamp(self):
        sm.init_state("DX-2026-001")
        sm.append_history("DX-2026-001", "A2", "start", "")
        state = sm.load_state("DX-2026-001")
        assert "timestamp" in state["history"][0]


# ─────────────────────────────────────────────────────────────────────────────
# Tests: contract helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestContractHelpers:
    def test_update_contract_approved_advances_status(self):
        sm.init_state("DX-2026-001")
        sm.update_contract("DX-2026-001", "blackboard/contracts/DX-2026-001_contract.json", "approved")
        state = sm.load_state("DX-2026-001")
        assert state["contract"]["status"] == "approved"
        assert state["status"] == "contract_approved"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: completion helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestCompletionHelpers:
    def test_get_next_pending_returns_first_pending(self):
        sm.init_state("DX-2026-001")
        nxt = sm.get_next_pending("DX-2026-001")
        assert nxt == "A1_estrategia"

    def test_get_next_pending_skips_complete(self):
        sm.init_state("DX-2026-001")
        sm.update_dimension("DX-2026-001", "A1_estrategia", {"status": "complete"})
        nxt = sm.get_next_pending("DX-2026-001")
        assert nxt == "A2_liderazgo"

    def test_get_next_pending_returns_none_when_all_started(self):
        sm.init_state("DX-2026-001")
        for key in sm.DIMENSION_KEYS:
            sm.update_dimension("DX-2026-001", key, {"status": "complete"})
        nxt = sm.get_next_pending("DX-2026-001")
        assert nxt is None

    def test_is_all_dimensions_complete_false_initially(self):
        sm.init_state("DX-2026-001")
        assert sm.is_all_dimensions_complete("DX-2026-001") is False

    def test_is_all_dimensions_complete_true_when_all_done(self):
        sm.init_state("DX-2026-001")
        for key in sm.DIMENSION_KEYS:
            sm.update_dimension("DX-2026-001", key, {"status": "complete"})
        assert sm.is_all_dimensions_complete("DX-2026-001") is True

    def test_is_all_dimensions_evaluated_requires_eval_passed(self):
        sm.init_state("DX-2026-001")
        for key in sm.DIMENSION_KEYS:
            sm.update_dimension("DX-2026-001", key, {"status": "evaluated", "eval_passed": True})
        assert sm.is_all_dimensions_evaluated("DX-2026-001") is True

    def test_is_all_dimensions_evaluated_false_if_any_failed(self):
        sm.init_state("DX-2026-001")
        for key in sm.DIMENSION_KEYS:
            sm.update_dimension("DX-2026-001", key, {"status": "evaluated", "eval_passed": True})
        sm.update_dimension("DX-2026-001", "A3_cultura", {"eval_passed": False})
        assert sm.is_all_dimensions_evaluated("DX-2026-001") is False
