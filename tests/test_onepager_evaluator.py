# tests/test_onepager_evaluator.py
from unittest.mock import MagicMock, patch
import asyncio
import pytest

A10_PASS = {
    "aprobado": True,
    "criterios_fallidos": [],
    "feedback": "",
    "puntuacion": 95,
}
A10_FAIL = {
    "aprobado": False,
    "criterios_fallidos": ["No menciona cifras específicas"],
    "feedback": "Agregar ROI cuantificado en términos financieros.",
    "puntuacion": 60,
}
SAMPLE_ONEPAGER = {
    "situacion_actual": "Empresa con baja madurez digital en procesos clave.",
    "hallazgos": [{"observable": "h1", "consecuencia": "c1"}],
    "causas_raiz": ["cr1"],
    "costo_no_actuar": {"mensual": "$50,000 MXN"},
    "camino": {"fase_1": "Diagnóstico"},
    "texto_completo_md": "# One Pager\n\nContenido ejecutivo completo del diagnóstico.",
}


def _make_sm_mock():
    """state_manager mock where load_state raises FileNotFoundError → retry_count=0."""
    sm = MagicMock()
    sm.load_state.side_effect = FileNotFoundError
    return sm


def test_run_onepager_evaluation_calls_a10():
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = A10_PASS

    with patch("orchestrator.onepager_evaluator.state_manager", _make_sm_mock()), \
         patch("orchestrator.onepager_evaluator._save_onepager_evaluation"):
        from orchestrator.onepager_evaluator import run_onepager_evaluation
        passed, feedback = asyncio.get_event_loop().run_until_complete(
            run_onepager_evaluation(
                diagnostico_id="DX-2026-001",
                onepager_output=SAMPLE_ONEPAGER,
                runner=mock_runner,
            )
        )

    mock_runner.run_agent_session.assert_called_once()
    assert mock_runner.run_agent_session.call_args[0][0] == "A10"
    assert passed is True


def test_run_onepager_evaluation_propagates_fail():
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = A10_FAIL

    with patch("orchestrator.onepager_evaluator.state_manager", _make_sm_mock()), \
         patch("orchestrator.onepager_evaluator._save_onepager_evaluation"):
        from orchestrator.onepager_evaluator import run_onepager_evaluation
        passed, feedback = asyncio.get_event_loop().run_until_complete(
            run_onepager_evaluation(
                diagnostico_id="DX-2026-001",
                onepager_output=SAMPLE_ONEPAGER,
                runner=mock_runner,
            )
        )

    assert passed is False
    assert len(feedback) > 0
