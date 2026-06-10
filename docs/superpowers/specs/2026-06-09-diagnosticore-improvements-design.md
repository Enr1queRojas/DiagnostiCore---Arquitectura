# DiagnostiCore — Mejoras v3 (2026-06-09)

## Contexto

Evaluación y rediseño integral del sistema agéntico DiagnostiCore v2. Análisis de 15 debilidades identificadas en el código fuente, implementadas en 4 capas de dependencia (Capa 0 → 3).

---

## Debilidades identificadas

| # | Componente | Problema |
|---|-----------|---------|
| 1 | `blackboard.py` + `agent_runner.py` | `ANTIPATRONES_VALIDOS` duplicado en 3 lugares — frozenset hardcoded en agent_runner, lista en blackboard, contenido en antipatterns.json |
| 2 | `quality_gate.py`, `onepager_evaluator.py`, `agent_runner.py` | Escalación de quality-gate requería **tercera llamada** a `run_quality_gate()` solo para disparar el error — desperdicia 1 round-trip LLM |
| 3 | `state_manager.py` | Archivo de estado **singleton** (`blackboard/diagnostico-state.json`) — diagnósticos concurrentes se pisan |
| 4 | `agent_runner.py` | **Sin timeouts** en `asyncio.to_thread(runner.run_agent_session...)` — una llamada colgada bloquea todo el pipeline |
| 5 | `agent_runner.py` | **Sin resumabilidad** — si el proceso muere después de 3/6 dimensiones, el restart re-ejecuta todo desde cero |
| 6 | `agent_runner.py` | **A11 no existía** — el pipeline terminaba en A8 sin el agente de reporte completo |
| 7 | `contract_builder.py` | Fallo en state update después de construir contrato se **silenciaba** con `logger.warning` — el orquestador pierde tracking del contrato |
| 8 | `blackboard.py` | `AGENTES_VALIDOS` no incluía CB, A9, A10, A11 — `marcar_agente_completado()` rechazaba agentes válidos |
| 9 | `quality_gate.py`, `onepager_evaluator.py`, `contract_builder.py` | Cada módulo tenía su **propio loader de JSON** — cambiar un path requería editar 4+ archivos |
| 10 | `quality_gate.py` | Usaba loaders locales en lugar de la cache centralizada — misma config leída N veces por run |
| 11 | `agent_runner.py` | A1–A6 corrían en paralelo pero no se guardaba cuáles **ya completaron** — sin harness resume pattern |
| 12 | `blackboard.py` | No existía `write_reporte_completo()` para el output de A11 |
| 13 | `blackboard.py` | `exportar_para_agente()` sin routing para A11 |
| 14 | `CLAUDE.md` | Referenciaba `blackboard/diagnostico-state.json` (path obsoleto) |
| 15 | `agent_runner.py` | Phase 3 ejecutaba A8 solo; A11 no existía en el pipeline |

---

## Decisiones de diseño

**Backward compatibility**: Tabla rasa aceptable — libertad máxima de rediseño.

**Prioridad**: Todas las categorías (robustez, arquitectura, calidad de output, deuda técnica).

**Enfoque**: Barrido integral por capas, en orden de dependencia inversa.

---

## Cambios implementados

### Capa 0 — Single source of truth para anti-patrones

**Archivos**: `config/antipatterns.json`, `config/config_loader.py` (nuevo)

- Agrega campo `ids_validos` a `antipatterns.json` v2.1 como array canónico
- Crea `config/config_loader.py` con `@lru_cache(maxsize=1)` en todos los loaders
- Expone: `load_antipattern_ids()`, `load_antipatterns_for_dimension()`, `load_antipatterns_summary()`, `load_maturity_scale_for_dimension()`, `load_acceptance_criteria()`, `load_pesos_idd()`, `invalidate_cache()`
- Todos los módulos que antes leían JSON directamente ahora importan `config_loader`

### Capa 1 — State manager multi-run

**Archivo**: `orchestrator/state_manager.py`

- Reemplaza singleton `_STATE_FILE = blackboard/diagnostico-state.json` por función `_state_file(run_id) → Path`
- Nuevo directorio: `blackboard/state/{run_id}-state.json`
- Todas las funciones públicas reciben `diagnostico_id` y usan `_state_file(diagnostico_id)` para lock paths
- Escritura atómica vía `.tmp` → `replace()` preservada
- Elimina `_assert_id()` de funciones de update (el path ya es por run_id, no puede confundirse)

### Capa 2a — Quality gate: eliminar tercera llamada

**Archivo**: `orchestrator/quality_gate.py`

- Reemplaza `_load_maturity_scale()` y `_load_antipatterns()` locales con `config_loader`
- Después de actualizar `retry_count`: si `new_retry_count >= 2` y no pasó → `raise QualityGateEscalationError` inmediatamente
- Ya no es necesaria una tercera llamada desde `agent_runner.py`
- Mismo patrón aplicado a `orchestrator/onepager_evaluator.py`

### Capa 2b — Contract builder: falla explícita

**Archivo**: `orchestrator/contract_builder.py`

- Reemplaza `_load_antipatterns_summary()` local con `config_loader.load_antipatterns_summary()`
- Fallo en `state_manager.update_contract()` ahora lanza `OrchestratorError` en lugar de `logger.warning`
- Elimina `_CONFIG_DIR` y `_AGENTS_DIR` (ya no se usan)
- Importa `OrchestratorError` directamente

### Capa 2c — Agent runner: A11 + timeouts + resumabilidad + retry fix

**Archivo**: `orchestrator/agent_runner.py`

- `_VALID_ANTIPATTERNS` ahora es `config_loader.load_antipattern_ids()` — elimina frozenset hardcoded
- Agrega `_SCHEMA_REPORTE_COMPLETO` y lo registra en `_SCHEMA_MAP["A11"]`
- Agrega routing `A11 → blackboard.write_reporte_completo()` en `_write_to_blackboard()`
- **Timeouts**: `asyncio.wait_for(..., timeout=300.0)` en el `asyncio.to_thread` de cada agente
- **Resumabilidad**: antes del `asyncio.gather`, consulta `state_manager.load_state()` y omite dimensiones con status `complete`/`evaluated`; restaura sus resultados desde el blackboard
- **Fix retry loop**: elimina tercera llamada a `run_quality_gate()` (ahora la segunda llamada ya puede escalar)
- **Phase 3 paralela**: A8 y A11 corren con `asyncio.gather()`; fallo de A11 es no-fatal (warning + continúa); fallo de A8 es fatal

### Capa 3 — Blackboard

**Archivo**: `blackboard/blackboard.py`

- `AGENTES_VALIDOS` expandido a `["CB", "A1", ..., "A6", "A7", "A8", "A9", "A10", "A11"]`
- `ANTIPATRONES_VALIDOS` ahora se carga desde `config_loader.load_antipattern_ids()` en lugar de lista hardcoded
- Agrega `write_reporte_completo(reporte)` — valida precondición (One-Pager completado), escribe y llama `marcar_agente_completado("A11")`
- Agrega routing A11 en `exportar_para_agente()` — expone síntesis + resultados dimensionales + cliente (sin One-Pager, ya que A8+A11 corren en paralelo)

### CLAUDE.md

- Actualiza referencia de estado: `blackboard/diagnostico-state.json` → `blackboard/state/{run_id}-state.json`
- Actualiza pipeline a v3: documenta ejecución paralela de A1–A6, Phase 3 (A8+A11 paralelo), y escalación directa sin tercera llamada
- Actualiza tabla de agentes: A1–A10 → A1–A11

---

## Invariantes que no cambiaron

- Máximo 3 causas raíz en síntesis (validado en `blackboard.write_sintesis()`)
- One-Pager requiere aprobación de A10 antes de ser entregable
- Contrato se genera siempre antes de lanzar agentes dimensionales
- Quality-gate (A9) se ejecuta después de cada A1–A6
- Escalación máx 2 retries por dimensión (y por One-Pager)
- Escritura atómica en todos los archivos de estado

---

## Archivos modificados

| Archivo | Tipo de cambio |
|---------|---------------|
| `config/antipatterns.json` | +`ids_validos`, `_meta.version` → 2.1 |
| `config/config_loader.py` | Nuevo archivo |
| `orchestrator/state_manager.py` | Multi-run state files |
| `orchestrator/quality_gate.py` | config_loader + escalación directa |
| `orchestrator/contract_builder.py` | config_loader + OrchestratorError |
| `orchestrator/onepager_evaluator.py` | config_loader + escalación directa |
| `orchestrator/agent_runner.py` | A11 + timeouts + resumabilidad + Phase 3 paralela |
| `blackboard/blackboard.py` | AGENTES_VALIDOS + write_reporte_completo + A11 routing |
| `CLAUDE.md` | Estado pipeline v3 |
