# tests/test_main.py
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import importlib


def test_main_imports_session_runner_not_llm_client():
    """main.py must import SessionRunner and setup_managed_agents, not AsyncLLMClient."""
    import ast
    from pathlib import Path
    src = (Path(__file__).parent.parent / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.dump(node))
    imports_str = " ".join(imports)
    assert "SessionRunner" in imports_str, "main.py must import SessionRunner"
    assert "setup_managed_agents" in imports_str, "main.py must import setup_managed_agents"
    assert "AsyncLLMClient" not in imports_str, "main.py must NOT import AsyncLLMClient"


def test_setup_flag_exists_in_parser():
    """--setup argument must be registered in _build_parser()."""
    # Stub heavy imports before importing main
    stubs = [
        "auth.jwt_auth", "blackboard.blackboard",
        "orchestrator.session_runner", "orchestrator.managed_agent_setup",
    ]
    with patch.dict(sys.modules, {s: MagicMock() for s in stubs}):
        # Stub orchestrator itself
        orch_stub = MagicMock()
        orch_stub.OrchestratorError = Exception
        orch_stub.run_full_pipeline = AsyncMock()
        with patch.dict(sys.modules, {"orchestrator": orch_stub}):
            import main as main_mod
            importlib.reload(main_mod)
            parser = main_mod._build_parser()
            args = parser.parse_args(["--setup"])
            assert args.setup is True
