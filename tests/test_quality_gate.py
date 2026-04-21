# tests/test_quality_gate.py
from unittest.mock import MagicMock, patch
import pytest

A9_PASS_VERDICT = {
    "aprobado": True,
    "puntuacion": 90,
    "hallazgos": [],
    "feedback": "",
}
A9_FAIL_VERDICT = {
    "aprobado": False,
    "puntuacion": 55,
    "hallazgos": ["Missing anti-pattern analysis"],
    "feedback": "Incluir análisis de antipatrones detectados.",
}
SAMPLE_DIMENSION_OUTPUT = {
    "nivel_madurez": 2,
    "justificacion": "Evidencia insuficiente para nivel superior.",
    "hallazgos_principales": ["h1"],
    "antipatrones_detectados": [],
    "traduccion_negocio": "biz",
    "senal_de_alerta_critica": "none",
}


def test_run_quality_gate_calls_a9_with_runner():
    """run_quality_gate() uses runner.run_agent_session('A9', ...), not llm_client."""
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = A9_PASS_VERDICT

    with patch("orchestrator.quality_gate.state_manager"), \
         patch("orchestrator.quality_gate._save_evaluation"):
        from orchestrator.quality_gate import run_quality_gate
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            run_quality_gate(
                diagnostico_id="DX-2026-001",
                dimension_key="A1_estrategia",
                dimensional_output=SAMPLE_DIMENSION_OUTPUT,
                runner=mock_runner,
            )
        )

    mock_runner.run_agent_session.assert_called_once()
    call_args = mock_runner.run_agent_session.call_args[0]
    assert call_args[0] == "A9"
    assert isinstance(call_args[1], dict)  # context dict
    passed, feedback = result
    assert passed is True


def test_run_quality_gate_returns_fail_with_feedback():
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = A9_FAIL_VERDICT

    with patch("orchestrator.quality_gate.state_manager"), \
         patch("orchestrator.quality_gate._save_evaluation"):
        from orchestrator.quality_gate import run_quality_gate
        import asyncio
        passed, feedback = asyncio.get_event_loop().run_until_complete(
            run_quality_gate(
                diagnostico_id="DX-2026-001",
                dimension_key="A2_liderazgo",
                dimensional_output=SAMPLE_DIMENSION_OUTPUT,
                runner=mock_runner,
            )
        )

    assert passed is False
    assert len(feedback) > 0
