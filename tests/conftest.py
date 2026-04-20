# tests/conftest.py
"""
Pytest configuration: stub out heavy transitive imports that are not
installed in the test environment so that lightweight orchestrator modules
(e.g. managed_agent_setup, state_manager) can be imported without pulling
in the full FastAPI / SSE / OpenTelemetry stack.

Import chain that requires stubbing:
    orchestrator/__init__.py
      → agent_runner
          → opentelemetry.trace
          → api.sse          → api.app → sse_starlette
          → blackboard.blackboard
          → mcp_adapter.pii_filter
          → telemetry.tracing
"""
import sys
import types


def _make_stub(name: str) -> types.ModuleType:
    """Return a fresh stub module, inserted into sys.modules."""
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def _ensure_stub(name: str) -> types.ModuleType:
    """Return existing module or create a stub; also ensure all parent packages exist."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        prefix = ".".join(parts[:i])
        if prefix not in sys.modules:
            _make_stub(prefix)
    return sys.modules[name]


# ── opentelemetry ──────────────────────────────────────────────────────────────
ot_trace = _ensure_stub("opentelemetry.trace")
ot_trace.Status = object
ot_trace.StatusCode = object

# ── sse_starlette ──────────────────────────────────────────────────────────────
sse_mod = _ensure_stub("sse_starlette.sse")
sse_mod.EventSourceResponse = object  # type: ignore[attr-defined]

# ── api.sse / api.app ──────────────────────────────────────────────────────────
api_sse = _ensure_stub("api.sse")
api_sse.event_bus = types.SimpleNamespace(emit=lambda *a, **kw: None)  # type: ignore[attr-defined]
_ensure_stub("api.app")

# ── blackboard ────────────────────────────────────────────────────────────────
bb = _ensure_stub("blackboard.blackboard")
bb.Blackboard = object          # type: ignore[attr-defined]
bb.BlackboardError = Exception  # type: ignore[attr-defined]

# ── mcp_adapter ───────────────────────────────────────────────────────────────
pii = _ensure_stub("mcp_adapter.pii_filter")
pii.filter_evidence_dict = lambda x: x  # type: ignore[attr-defined]

# ── telemetry ─────────────────────────────────────────────────────────────────
tel = _ensure_stub("telemetry.tracing")
tel.get_tracer = lambda *a, **kw: None  # type: ignore[attr-defined]
