# DiagnostiCore Harness v3 — Design Spec

**Date:** 2026-04-07
**Status:** Approved for implementation
**Approach:** B — Full Harness v3 (comprehensive refactor)
**Branch:** `feature/harness-v3`

---

## 1. Goal

Refactor DiagnostiCore to fully adopt the Harness Methodology from *The Autonomous Agent Blueprint*. The system already implements Harness v2 (state persistence, contracts, A9/A10 evaluators). v3 closes the remaining structural gaps so that the pipeline can be reasoned about, tested, and resumed phase-by-phase with explicit Shift-Worker lifecycle steps.

## 2. Non-Goals

- Browser automation / Playwright human surrogates (irrelevant for a JSON-output system).
- Separate Planner/Generator/Evaluator tri-agent split (A1–A10 already separate generation from evaluation).
- Context window compaction (each agent runs in a fresh LLM call).
- New persistence backend.
- Prompt rewrites for agents A1–A10.

## 3. Design Decisions (Confirmed)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | A1–A6 stay parallel (`asyncio.gather`) | They are data-independent. Parallelism reduces wall-clock from 6× to 1× LLM latency. The Shift-Worker pattern applies at the *phase* level, not within parallel siblings. |
| 2 | `Context_Node` is a block inside `diagnostico-state.json` (not a separate file) | Re-uses existing file lock; no I/O overhead; backward-compatible. |
| 3 | Verification matrix is a deterministic pre-validator that runs **before** A9 | "Compensatory Scaffold" pattern. Cheap structural checks eliminate obvious failures and save LLM calls. |
| 4 | Round files overwrite a single output (e.g. `_A4.json`) — round history is the audit trail | Lean disk usage; consultant can still see *what changed* via `build_rounds[].feedback_summary`. |
| 5 | `track_clean_runs=False` by default — only failed dimensions get a `build_rounds` entry | State stays lean; the presence of an entry signals "this dimension needed attention." |

## 4. Module Map

### 4.1 New files

| File | Purpose |
|------|---------|
| `orchestrator/harness.py` | `Harness` coordinator + 4 phase functions (planning, dimensional_sprint, synthesis, output). |
| `orchestrator/agent_runner_v2.py` | `AgentRunner` class with 5 explicit Shift-Worker methods. |
| `orchestrator/verification_matrix.py` | Rule-based pre-validator. |
| `orchestrator/build_rounds.py` | Round naming, persistence, diff helpers. |
| `tests/test_harness.py` | Phase-function unit tests. |
| `tests/test_agent_runner_v2.py` | AgentRunner lifecycle tests. |
| `tests/test_verification_matrix.py` | Rule-function tests. |
| `tests/test_build_rounds.py` | Round tracking tests. |
| `tests/test_pipeline_integration.py` | End-to-end with mocked LLM. |

### 4.2 Modified files

| File | Change |
|------|--------|
| `orchestrator/state_manager.py` | Add `write_handoff/read_handoff/clear_handoff/start_round/complete_round/get_round_history/get_current_round`. Bump `schema_version` to `3.0`. Auto-upgrade `2.0` files on read. |
| `orchestrator/agent_runner.py` | `_execute_pipeline()` becomes a shim around `Harness.run()`. `run_agent()` becomes a shim around `AgentRunner.execute()`. Public signatures preserved. |
| `orchestrator/quality_gate.py` | Call `verification_matrix.verify()` first; skip A9 LLM call on critical failure. |
| `orchestrator/__init__.py` | Re-export `Harness`, `AgentRunner`. |
| `config/acceptance_criteria.json` | Convert to per-agent map. Existing A10 criteria become the `A10` key. |
| `blackboard/diagnostico-state.json` (template) | Add `context_node` and `build_rounds` blocks. |

### 4.3 Unchanged

`main.py`, `api/app.py`, `api/sse.py`, `blackboard/blackboard.py`, all `agents/*.md` prompt files.

## 5. Module Dependency Graph

```
main.py
  └─ orchestrator.run_full_pipeline()                       [thin shim]
       └─ Harness.run()                                     [harness.py]
            ├─ phase_planning()
            │     └─ contract_builder.build_contract()
            ├─ phase_dimensional_sprint()
            │     └─ asyncio.gather(AgentRunner.execute() × 6)
            │     └─ phase_quality_gate()
            │           ├─ verification_matrix.verify()    [deterministic]
            │           └─ quality_gate.run_quality_gate() [LLM, only if matrix passes]
            ├─ phase_synthesis()
            │     └─ AgentRunner.execute(A7)
            └─ phase_output()
                  ├─ AgentRunner.execute(A8)
                  └─ onepager_evaluator.run_onepager_evaluation()
```

## 6. Data Model

### 6.1 `context_node` block

Added to `diagnostico-state.json`. The Minimal Viable Context handed off between phases.

```json
{
  "context_node": {
    "current_phase": "dimensional_sprint",
    "next_phase": "quality_gate",
    "produced_by": "phase_planning",
    "produced_at": "2026-04-07T12:34:56Z",
    "consumed_at": null,
    "payload": { "...": "phase-specific dict" },
    "checksum": "sha256:abcd...",
    "history": [
      {
        "phase": "phase_planning",
        "produced_at": "...",
        "consumed_at": "...",
        "payload_keys": ["contract_path", "evidence_keys", "client_summary"]
      }
    ]
  }
}
```

**Invariants:**
- `payload` is opaque to `state_manager`. Each phase serialises a typed dataclass via `dataclasses.asdict()`.
- `checksum` = SHA-256 of canonical JSON of `payload`. Verified on read. Mismatch → `ContextNodeIntegrityError`.
- `history` keeps the last 20 handoffs. Stores only `payload_keys`, never the payload itself (this is the context-release mechanism).
- `consumed_at` tracks the read. A second read of an already-consumed node triggers fallback to durable artifacts (`blackboard/outputs/*.json`).

### 6.2 `build_rounds` block

```json
{
  "build_rounds": {
    "A4_procesos": {
      "current_round": 2,
      "rounds": [
        { "round_id": "round_1",    "agent": "A4", "outcome": "generated", "...": "..." },
        { "round_id": "round_1_qa", "agent": "A9", "outcome": "fail", "feedback_summary": "...", "...": "..." },
        { "round_id": "round_2",    "agent": "A4", "outcome": "running",   "...": "..." }
      ]
    }
  }
}
```

**Invariants:**
- Only dimensions that failed at least one round get an entry (`track_clean_runs=False`).
- Output files (`blackboard/outputs/<run>_<agent>.json`) are overwritten per round; the audit trail lives in `build_rounds[].feedback_summary`.
- `trigger` ∈ {`initial_run`, `qa_feedback_round_N`, `manual_retry`, `escalation_recovery`}.

### 6.3 New state_manager API

```python
# Context_Node
def write_handoff(diagnostico_id, current_phase, next_phase, payload, produced_by) -> None
def read_handoff(diagnostico_id, expected_phase) -> dict
    # `expected_phase` = the consumer's phase name. Asserts that the stored
    # node's `next_phase` matches; raises HandoffMismatchError otherwise.
def clear_handoff(diagnostico_id) -> None

# BuildRound
def start_round(diagnostico_id, dim_key, agent, trigger) -> str   # returns round_id
def complete_round(diagnostico_id, dim_key, round_id, outcome,
                   output_path=None, eval_path=None, score=None,
                   feedback_summary=None) -> None
def get_round_history(diagnostico_id, dim_key) -> list[dict]
def get_current_round(diagnostico_id, dim_key) -> int
```

All functions acquire the existing file lock — no new locking mechanism.

## 7. Phase Functions (Shift-Worker Lifecycle)

Every `_phase_*` method follows the identical 5-step pattern:

```
1. LOAD STATE       — read_handoff(expected_phase=...)
2. EXECUTE          — do the work (contract / agents / synthesis / output)
3. VALIDATE         — verification_matrix.verify() then quality_gate / onepager_evaluator
4. WRITE HANDOFF    — write_handoff(payload=asdict(TypedHandoff))
5. RELEASE CONTEXT  — update_pipeline_status(); drop in-memory references
```

### 7.1 Typed handoff payloads

```python
@dataclass
class PlanningHandoff:
    contract_path: str
    evidence_keys: list[str]
    client_summary: dict
    dimensions_to_run: list[str]

@dataclass
class DimensionalHandoff:
    output_paths: dict[str, str]
    failed_dimensions: list[str]
    rounds_used: dict[str, int]

@dataclass
class SynthesisHandoff:
    sintesis_path: str
    idd: float
    causas_raiz_count: int

@dataclass
class OutputHandoff:
    onepager_path: str
    eval_passed: bool
    delivered: bool
```

### 7.2 `Harness` coordinator

```python
class Harness:
    def __init__(self, run_id, blackboard, llm_client, track_clean_runs=False): ...
    async def run(self) -> dict[str, dict]:
        results = {}
        await self._phase_planning()
        await self._phase_dimensional_sprint(results)
        await self._phase_synthesis(results)
        await self._phase_output(results)
        return results
```

## 8. AgentRunner Class (Per-Agent Shift-Worker)

```python
class AgentRunner:
    def __init__(self, blackboard, llm_client): ...

    async def execute(self, agent_id, run_id) -> dict:
        ctx       = self.load_context(agent_id, run_id)
        raw       = await self.execute_task(agent_id, ctx)
        validated = await self.validate_output(agent_id, raw, ctx)
        await self.structure_handoff(agent_id, validated)
        self.release_context(ctx)
        return validated

    def      load_context(self, agent_id, run_id) -> AgentContext: ...
    async def execute_task(self, agent_id, ctx) -> str: ...
    async def validate_output(self, agent_id, raw, ctx) -> dict: ...
    async def structure_handoff(self, agent_id, validated) -> None: ...
    def      release_context(self, ctx) -> None: ...
```

`AgentContext` is a frozen dataclass: `(system_prompt, evidence_subset, run_metadata, context_node_ref)`.

The legacy `run_agent()` becomes a backward-compat shim:

```python
async def run_agent(agent_id, run_id, blackboard, llm_client):
    return await AgentRunner(blackboard, llm_client).execute(agent_id, run_id)
```

## 9. Verification Matrix

### 9.1 Extended `acceptance_criteria.json` (v2.0)

Per-agent map. Each criterion has:
- `id` — stable identifier (e.g. `A1.evidencia_minima`)
- `type` — `structural` (deterministic) or `semantic` (LLM-judged)
- `rule` — name of the matrix rule function
- `params` — rule-specific parameters
- `severity` — `critical` (blocks) or `warning` (forwarded to A9)
- `description` — human-readable explanation (used in feedback)

### 9.2 Built-in rules

| Rule name | Purpose |
|-----------|---------|
| `field.list_length` | Checks `min`/`max` length of a list field. |
| `field.numeric_range` | Checks numeric field is within `[min, max]`. |
| `field.min_length` | Checks string field has min character length. |
| `justificacion.min_sources` | Counts distinct evidence sources cited in `justificacion`. |
| `text.no_forbidden_terms` | Checks a text field for forbidden technical jargon. |
| `nested.list_length` | JSONPath-style nested length check (e.g. `causas_raiz[*].evidencia`). |

### 9.3 `verification_matrix.verify()` API

```python
@dataclass
class MatrixResult:
    passed: bool                # True if no critical failures
    failures: list[dict]        # critical failures (block the agent)
    warnings: list[dict]        # warnings (forwarded to A9/A10)
    feedback_for_agent: str     # human-readable summary

def verify(agent_id: str, output: dict) -> MatrixResult: ...
```

### 9.4 Quality gate integration

```python
# At the top of run_quality_gate(), BEFORE the LLM call:
matrix_result = verification_matrix.verify(agent_id, dimensional_output)
if not matrix_result.passed:
    state_manager.append_history(diagnostico_id, "verification_matrix", "fail",
                                 f"dim={dimension_key} failures={len(matrix_result.failures)}")
    return False, matrix_result.feedback_for_agent
# Otherwise: A9 runs with warnings forwarded as additional input
```

## 10. Migration Strategy (Zero-Downtime)

| Step | Action | Risk |
|------|--------|------|
| 1 | Add new files. No existing code touched. | None |
| 2 | Extend `state_manager.py`. Bump schema_version to `3.0`. Auto-upgrade `2.0` files on read (in-memory inject empty `context_node`/`build_rounds`). | Low |
| 3 | Extend `acceptance_criteria.json` to per-agent map. Keep legacy reader for one release cycle. | Low |
| 4 | Replace `_execute_pipeline()` body with `Harness().run()`. | Medium |
| 5 | Wire `verification_matrix.verify()` into `quality_gate.py`. | Low |
| 6 | Run pytest + end-to-end against `examples/CompoLat_ejemplo.json`. | None |

**Rollback:** `_execute_pipeline()` is now a shim. `git revert <merge-commit>` is sufficient. Schema upgrade is non-destructive and idempotent.

## 11. Testing Strategy

| Test file | Coverage |
|-----------|----------|
| `tests/test_state_manager.py` (extend) | New handoff/round APIs, checksum integrity, history rotation, `2.0 → 3.0` auto-upgrade. |
| `tests/test_build_rounds.py` (new) | Round numbering, trigger validation, `track_clean_runs=False` skip. |
| `tests/test_verification_matrix.py` (new) | Each rule fn in isolation, severity ladder, feedback formatting. |
| `tests/test_harness.py` (new) | Each `_phase_*` method with mocked AgentRunner. Verifies lifecycle order. |
| `tests/test_agent_runner_v2.py` (new) | The 5 lifecycle methods independently. Mocked AsyncLLMClient. |
| `tests/test_pipeline_integration.py` (new) | End-to-end with mocked LLM responses, replays `examples/CompoLat_ejemplo.json`. |

**Coverage goal:** every public function in new modules has at least one happy-path and one failure-path test.

## 12. Code Style

- Python 3.11+, async/await throughout.
- All new code commented in **English** (project convention from this spec).
- `logging.getLogger(__name__)` — never `print()`.
- `dataclasses` for typed payloads.
- Type hints on every public function.
- Cross-platform file locking via the existing `_acquire_lock`/`_release_lock` helpers in `state_manager.py`.

## 13. Open Questions

None. All clarifications resolved during brainstorming session.

## 14. References

- *The Autonomous Agent Blueprint* — Harness Methodology (PDF, 179 pages).
- Anthropic Harness Design article (referenced in `state_manager.py` docstring).
- DiagnostiCore CLAUDE.md (project conventions).
- DiagnostiCore SKILL.md (architecture & business rules).
- Memory: `project_harness_v2.md` (the v2 baseline this spec evolves).
