# DiagnostiCore — Sistema Agéntico de Diagnóstico 360
## InnoVerse Solutions | Harness v3 | Confidencial

> *"El 70–80% de los fracasos en transformación digital tiene causas organizacionales, no técnicas."*
> — MIT CISR (Ross, Weill, Sebastian, 2019)

---

## ¿Qué es esto?

**DiagnostiCore** es el sistema agéntico de InnoVerse que convierte evidencia cruda de un levantamiento de diagnóstico en entregables ejecutivos accionables. Diagnostica organizaciones en seis dimensiones de madurez digital, genera un árbol de causalidad, calcula el Índice de Deuda Digital (IDD), y produce en paralelo el One-Pager ejecutivo y el Reporte Completo de diagnóstico.

El sistema corre sobre **Claude Managed Agents** (beta): cada sub-agente es un objeto persistente en la nube con su propio system prompt y contexto. El harness orquesta sesiones por run, no llamadas directas al modelo.

---

## Pipeline v3

```
[Evidencia del cliente]
        │
        ▼
[CB — Contract Builder]
  Genera contrato específico del cliente
  (dimensiones prioritarias, anti-patrones esperados, criterios de calidad)
        │
        ▼
[A1–A6] Análisis dimensional (paralelo)
  Cada agente evalúa su dimensión (nivel 1–5)
  Lee el contrato del cliente como input adicional
        │ (por cada uno)
        ▼
[A9 — Quality Gate]
  Evalúa el output dimensional
  PASS → continúa
  FAIL → feedback → retry (máx 2×) → escala a humano
        │
        ▼
[A7 — Motor de Síntesis]
  Patrones transversales + árbol de causalidad
  Máx. 3 causas raíz
  Calcula IDD ponderado
  Cuantifica Cost of Delay
  Diseña camino DECA+ en 3 fases
        │
       ─┼────────────────────────┐
        ▼                        ▼
[A8 — One Pager]        [A11 — Reporte Completo]
  1 página ejecutiva        8–12 páginas con evidencia
  (paralelo)                (paralelo)
        │                        │
        ▼                        │
[A10 — Onepager Eval]            │
  Valida checklist 8 criterios   │
  PASS → entregable              │
  FAIL → feedback → retry (2×)   │
        │                        │
        ▼                        ▼
[ONE-PAGER APROBADO]    [REPORTE COMPLETO]
```

---

## Estructura del repositorio

```
DiagnostiCore — Arquitectura/
│
├── CLAUDE.md                        ← Instrucciones para Claude Code
├── SKILL.md                         ← Especificación completa del sistema (leer primero)
├── README.md                        ← Este archivo
├── main.py                          ← CLI: nuevo run, pipeline completo
├── requirements.txt
│
├── agents/                          ← System prompts de cada agente (A1–A11 + CB)
│   ├── A1_estrategia.md             Dimensión 1: Estrategia y Modelos de Negocio
│   ├── A2_liderazgo.md              Dimensión 2: Liderazgo y Organizaciones
│   ├── A3_cultura.md                Dimensión 3: Cultura y Gestión del Cambio
│   ├── A4_procesos.md               Dimensión 4: Procesos y Operaciones
│   ├── A5_datos.md                  Dimensión 5: Datos, Analítica e BI
│   ├── A6_tecnologia.md             Dimensión 6: Tecnología y Arquitectura Digital
│   ├── A7_sintesis.md               Motor de Síntesis — causas raíz + IDD
│   ├── A8_one_pager.md              Entregable ejecutivo (1 página)
│   ├── A9_quality_gate.md           Evaluador de outputs dimensionales
│   ├── A10_onepager_eval.md         Evaluador del One-Pager (checklist 8 criterios)
│   ├── A11_reporte_completo.md      Entregable completo (8–12 páginas)
│   └── CB_contract_builder.md       Generador de contrato pre-diagnóstico
│
├── orchestrator/                    ← Lógica de orquestación
│   ├── managed_agent_setup.py       Setup único: crea Agents en la nube (run una vez)
│   ├── session_runner.py            Ejecuta sesiones per-run con SSE streaming
│   ├── agent_runner.py              Orquesta el pipeline A1→A11
│   ├── contract_builder.py          Invoca CB y guarda el contrato
│   ├── quality_gate.py              Invoca A9, maneja retry logic
│   ├── onepager_evaluator.py        Invoca A10, maneja retry logic
│   ├── state_manager.py             Persiste estado entre retries
│   ├── exceptions.py                Tipos de error del pipeline
│   └── llm_client.py                [LEGACY — AsyncLLMClient] Mantenido para api/app.py
│
├── blackboard/                      ← Estado compartido entre agentes
│   ├── blackboard.py                Manager de lectura/escritura del estado
│   ├── schema.json                  Esquema JSON de validación
│   ├── template.json                Template vacío para nuevo run
│   ├── diagnostico-state.json       Estado activo del pipeline (retry counts, fases)
│   ├── contracts/                   Contratos generados por CB (uno por run)
│   ├── outputs/                     Outputs dimensionales A1–A6
│   ├── evaluations/                 Evaluaciones A9 por dimensión
│   ├── synthesis/                   Output de A7
│   └── onepager/                    Output de A8 + evaluación de A10
│
├── config/                          ← Configuración del sistema
│   ├── maturity_scales.json         Escalas 1–5 por dimensión con evidencias
│   ├── antipatterns.json            Catálogo v2.0 de 7 anti-patrones (canónico)
│   ├── acceptance_criteria.json     Checklist de 8 criterios para el One-Pager
│   ├── pesos_idd.json               Pesos del IDD por dimensión + rangos
│   └── brand_guidelines.json        Identidad visual y reglas de lenguaje InnoVerse
│
├── api/                             ← FastAPI REST + SSE (interfaz web)
│   ├── app.py                       Endpoints: POST /runs, GET /stream, GET /report
│   ├── models.py                    Pydantic models de request/response
│   └── sse.py                       Event bus para Server-Sent Events
│
├── auth/
│   └── jwt_auth.py                  Tokens Bearer por run (aislamiento multi-consultor)
│
├── mcp_adapter/                     ← Adaptadores MCP (herramientas para agentes)
│   ├── pii_filter.py                Filtra PII de evidencia antes de enviar al modelo
│   ├── blackboard_server.py         Servidor MCP: leer/escribir blackboard
│   ├── tools_server.py              Servidor MCP: calcular_idd, detectar_antipatrones
│   └── sandbox.py                   Sandbox de ejecución para herramientas MCP
│
├── telemetry/
│   └── tracing.py                   OpenTelemetry spans por agente
│
├── tools/                           ← Scripts de cómputo compartidos
│   ├── calcular_idd.py              Calcula IDD ponderado (0–100)
│   ├── detectar_antipatron.py       Detecta 7 anti-patrones en texto libre
│   └── cuantificar_costo.py         Calcula Cost of Delay con factores conservadores
│
├── tests/                           ← Suite de pruebas (py -3.11 -m pytest)
│   ├── conftest.py                  Stubs de dependencias pesadas (OTel, FastAPI, etc.)
│   ├── test_managed_agent_setup.py  Tests del setup único de Agents en la nube
│   ├── test_session_runner.py       Tests del SessionRunner (SSE, JSON parse, errores)
│   ├── test_agent_runner_integration.py
│   ├── test_quality_gate.py
│   ├── test_onepager_evaluator.py
│   ├── test_contract_builder.py
│   ├── test_state_manager.py
│   └── test_main.py
│
├── examples/
│   └── CompoLat_ejemplo.json        Diagnóstico de referencia (manufactura)
│
├── docs/
│   ├── arquitectura_diagrama.mermaid
│   └── superpowers/plans/           Planes de implementación históricos
│
├── runs/                            ← Diagnósticos por cliente (confidencial, nunca borrar)
│   └── CLIENTE_YYYYMMDD.json
│
└── legacy/                          ← Versiones anteriores de prompts (nunca borrar)
```

---

## Setup inicial (una sola vez)

El sistema usa **Claude Managed Agents**. Los Agents se crean una vez en la nube y se reutilizan en cada run:

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. Crear los 11 Agent objects en Anthropic (A1–A10 + CB)
python main.py --setup
# → Escribe config/managed_agents_config.json (gitignoreado)
```

Este paso solo se ejecuta **una vez por entorno**. Si `managed_agents_config.json` ya existe, el comando es no-op.

---

## Ejecutar un diagnóstico

```bash
# CLI directo
python main.py --run-id EMPRESA_20260426 --cliente "Nombre Empresa" --sector manufactura --consultor "Ana García"

# Ver estado del diagnóstico activo
python main.py --status
```

```python
# Desde Python
from orchestrator.session_runner import SessionRunner
from orchestrator.agent_runner import run_full_pipeline

runner = SessionRunner()
await run_full_pipeline(run_id="EMPRESA_20260426", runner=runner, runs_dir="runs")
```

```bash
# Vía API REST
uvicorn api.app:app --host 0.0.0.0 --port 8000

curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"cliente":"Empresa","sector":"manufactura","consultor":"Ana García","tamanio":"mediana","empleados":200}'

# El response incluye run_id + Bearer token
# Conectar al stream:
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/runs/<run_id>/stream
```

---

## Herramientas de cómputo

```bash
# IDD manual
python tools/calcular_idd.py '{"estrategia":2,"liderazgo":2,"cultura":1,"procesos":2,"datos":1,"tecnologia":3}'

# Detección de anti-patrones en texto libre
python tools/detectar_antipatron.py analizar "El director aprueba todo. Cada área tiene su propio Excel."
python tools/detectar_antipatron.py listar

# Cost of Delay (demo con caso CompoLat)
python tools/cuantificar_costo.py
```

---

## Tests

```bash
# Siempre usar Python 3.11
py -3.11 -m pytest tests/ -q
# → 40 passed
```

---

## Reglas invariables del sistema

| Regla | Descripción |
|-------|-------------|
| **3 causas raíz máximo** | Si hay más, el análisis no es suficientemente profundo |
| **La causa raíz casi nunca está en Tecnología** | Invariablemente en Estrategia, Liderazgo o Cultura |
| **Nunca mencionar frameworks al cliente** | Siempre traducir a lenguaje de negocio |
| **Factores de conservadurismo** | Costo ×70%, Revenue ×50% |
| **Evidencia multifuente** | Nunca asignar nivel de madurez por cuestionario único |
| **Un entregable único por cliente** | Ninguna sección puede copiarse entre diagnósticos |
| **A9 obligatorio después de cada A1–A6** | No se salta el quality gate |
| **A10 obligatorio antes de entregar** | El One-Pager no se entrega sin aprobación de A10 |

---

## Recursos de referencia

| Recurso | Ubicación |
|---------|-----------|
| Fundamento teórico completo | `InnoVerse_Book_Diagnostico_360_v1.docx` |
| Template Word del One-Pager | `ONE_PAGER_InnoVerse_template_v1.docx` |
| Especificación del sistema agéntico | `SKILL.md` |
| Ejemplo de diagnóstico bien construido | `examples/CompoLat_ejemplo.json` |
| Diagrama de arquitectura | `docs/arquitectura_diagrama.mermaid` |

---

*InnoVerse Solutions | DiagnostiCore Harness v3 | Uso exclusivo del equipo InnoVerse. Confidencial.*
