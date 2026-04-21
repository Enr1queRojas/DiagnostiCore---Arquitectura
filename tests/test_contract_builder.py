# tests/test_contract_builder.py
from unittest.mock import MagicMock, patch
import asyncio
import pytest

MOCK_CONTRACT = {
    "diagnostico_id": "DX-2026-001",
    "client": {"name": "Empresa X", "industry": "manufactura", "size": "mediana"},
    "generated_at": "2026-04-21T00:00:00+00:00",
    "dimensions": {
        "A1_estrategia": {
            "evidencia_requerida": ["transcripciones"],
            "evidencia_minima_nivel_3": "Evidencia de roadmap digital aprobado",
            "antipatrones_prioritarios": ["transformacion_sin_brujula"],
            "criterios_exito": "Output con justificación basada en evidencia",
        },
        "A2_liderazgo": {"evidencia_requerida": [], "evidencia_minima_nivel_3": "", "antipatrones_prioritarios": [], "criterios_exito": ""},
        "A3_cultura": {"evidencia_requerida": [], "evidencia_minima_nivel_3": "", "antipatrones_prioritarios": [], "criterios_exito": ""},
        "A4_procesos": {"evidencia_requerida": [], "evidencia_minima_nivel_3": "", "antipatrones_prioritarios": [], "criterios_exito": ""},
        "A5_datos": {"evidencia_requerida": [], "evidencia_minima_nivel_3": "", "antipatrones_prioritarios": [], "criterios_exito": ""},
        "A6_tecnologia": {"evidencia_requerida": [], "evidencia_minima_nivel_3": "", "antipatrones_prioritarios": [], "criterios_exito": ""},
    },
}


def test_build_contract_calls_cb_agent():
    """build_contract() calls runner.run_agent_session('CB', ...) not llm_client."""
    from orchestrator.session_runner import SessionRunner
    mock_runner = MagicMock(spec=SessionRunner)
    mock_runner.run_agent_session.return_value = MOCK_CONTRACT

    with patch("orchestrator.contract_builder.state_manager"), \
         patch("orchestrator.contract_builder._save_contract", return_value="blackboard/contracts/DX-2026-001_contract.json"):
        from orchestrator.contract_builder import build_contract
        result = asyncio.get_event_loop().run_until_complete(
            build_contract(
                diagnostico_id="DX-2026-001",
                client_info={"name": "Empresa X", "industry": "manufactura", "size": "mediana"},
                available_evidence=["transcripciones"],
                runner=mock_runner,
            )
        )

    mock_runner.run_agent_session.assert_called_once()
    assert mock_runner.run_agent_session.call_args[0][0] == "CB"
    assert result["diagnostico_id"] == "DX-2026-001"
    assert "dimensions" in result
