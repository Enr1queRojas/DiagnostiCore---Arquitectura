# tests/test_agent_runner_integration.py
"""Integration test: verifies agent_runner uses SessionRunner, not AsyncLLMClient."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call


MOCK_DIMENSIONAL_OUTPUT = {
    "nivel_madurez": 3,
    "justificacion": "Evidencia suficiente para nivel 3 con hallazgos claros.",
    "hallazgos_principales": ["h1", "h2"],
    "antipatrones_detectados": [],
    "traduccion_negocio": "biz impact",
    "senal_de_alerta_critica": "none",
}
MOCK_SYNTHESIS = {
    "scores_por_dimension": {d: 3 for d in
        ["estrategia", "liderazgo", "cultura", "procesos", "datos", "tecnologia"]},
    "idd": 50.0,
    "causas_raiz": [{"nombre": "c1", "descripcion": "desc de prueba aqui", "evidencia": ["e1"]}],
    "patrones_transversales": [],
    "costo_inaccion_mensual": "$10,000 MXN",
    "camino_transformacion": {},
    "narrativa_interna": "ok",
}
MOCK_ONEPAGER = {
    "situacion_actual": "Situacion actual del cliente con contexto suficiente.",
    "hallazgos": [],
    "causas_raiz": [],
    "costo_no_actuar": {},
    "camino": {},
    "texto_completo_md": "# One Pager\n\nContenido del one pager.",
}


def _make_mock_runner(dimensional_output=None, synthesis=None, onepager=None):
    """Build a SessionRunner mock that returns appropriate outputs per agent key."""
    dim = dimensional_output or MOCK_DIMENSIONAL_OUTPUT
    synth = synthesis or MOCK_SYNTHESIS
    op = onepager or MOCK_ONEPAGER

    mock_runner = MagicMock()
    def side_effect(agent_key, context, run_id):
        if agent_key in {"A1", "A2", "A3", "A4", "A5", "A6"}:
            return dim
        if agent_key == "A7":
            return synth
        if agent_key == "A8":
            return op
        return {}
    mock_runner.run_agent_session.side_effect = side_effect
    return mock_runner


def test_run_agent_uses_session_runner():
    """run_agent() calls runner.run_agent_session(), not llm_client.sample()."""
    from orchestrator.session_runner import SessionRunner

    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = MOCK_DIMENSIONAL_OUTPUT

    mock_blackboard = MagicMock()
    mock_blackboard.exportar_para_agente.return_value = {"evidencia": "test"}
    mock_blackboard._data = {}

    with patch("orchestrator.agent_runner.load_contract", return_value=None), \
         patch("orchestrator.agent_runner._validate_output"), \
         patch("orchestrator.agent_runner._write_to_blackboard", new_callable=AsyncMock), \
         patch("orchestrator.agent_runner.get_tracer") as mock_tracer, \
         patch("orchestrator.agent_runner.event_bus"):

        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer.return_value.start_as_current_span.return_value = mock_span

        result = asyncio.get_event_loop().run_until_complete(
            __import__("orchestrator.agent_runner", fromlist=["run_agent"]).run_agent(
                agent_id="A1",
                run_id="TEST_001",
                blackboard=mock_blackboard,
                runner=mock_runner,
            )
        )

    mock_runner.run_agent_session.assert_called_once_with("A1", {"evidencia": "test"}, "TEST_001")
    assert result == MOCK_DIMENSIONAL_OUTPUT


def test_run_full_pipeline_signature_accepts_session_runner():
    """run_full_pipeline() accepts SessionRunner as second positional param (not AsyncLLMClient)."""
    import inspect
    from orchestrator.agent_runner import run_full_pipeline
    from orchestrator.session_runner import SessionRunner

    sig = inspect.signature(run_full_pipeline)
    params = list(sig.parameters.keys())
    assert params[1] == "runner", f"Expected 'runner', got '{params[1]}'"
    # AsyncLLMClient must NOT appear in the type hint
    runner_annotation = sig.parameters["runner"].annotation
    assert "AsyncLLMClient" not in str(runner_annotation)
