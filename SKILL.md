# DiagnostiCore — InnoVerse Diagnóstico 360
### Sistema Agéntico de Diagnóstico de Transformación Digital

**Versión:** 2.0 — Harness v3
**Propietario:** InnoVerse Solutions
**Clasificación:** Confidencial — Uso exclusivo del equipo InnoVerse
**Última actualización:** Mayo 2026

---

## Índice

1. [Propósito y Contexto](#1-propósito-y-contexto)
2. [Arquitectura del Sistema Agéntico](#2-arquitectura-del-sistema-agéntico)
3. [Flujo de Orquestación Principal](#3-flujo-de-orquestación-principal)
4. [Sub-Agentes — Especificaciones Detalladas](#4-sub-agentes--especificaciones-detalladas)
5. [Herramientas y Scripts Compartidos](#5-herramientas-y-scripts-compartidos)
6. [Escala de Madurez Global 1–5](#6-escala-de-madurez-global-15)
7. [Framework DECA+](#7-framework-deca)
8. [Cálculo del Índice de Deuda Digital (IDD)](#8-cálculo-del-índice-de-deuda-digital-idd)
9. [Anti-Patrones Documentados](#9-anti-patrones-documentados)
10. [Entregables Finales](#10-entregables-finales)
11. [Protocolo de Sesión de Síntesis Interna](#11-protocolo-de-sesión-de-síntesis-interna)
12. [Reglas de Negocio Invariables](#12-reglas-de-negocio-invariables)
13. [Glosario de Frameworks](#13-glosario-de-frameworks)

---

## 1. Propósito y Contexto

### 1.1 Qué hace este sistema

**DiagnostiCore** es el sistema agéntico que automatiza y asiste la metodología de **Diagnóstico 360 de InnoVerse**: un análisis integral de seis dimensiones de transformación digital aplicado a organizaciones en Latinoamérica, con énfasis especial en PYMEs de México.

El sistema convierte evidencia cruda — transcripciones de entrevistas, cuestionarios de madurez, auditorías técnicas, mapas de procesos, series financieras — en **entregables ejecutivos accionables**: un One-Pager de una página para la dirección y un Reporte Completo de 8–12 páginas con trazabilidad de evidencia.

### 1.2 Principio rector

> *"El 70–80% de los fracasos en transformación digital tiene causas organizacionales, no técnicas."*
> — MIT CISR (Ross, Weill, Sebastian, 2019)

Las seis dimensiones de InnoVerse forman un **sistema acoplado**, no compartimentos independientes. La causa raíz casi nunca está en Tecnología; invariablemente reside en Estrategia, Liderazgo o Cultura. DiagnostiCore está diseñado para respetar esta lógica causal.

### 1.3 Cadena dimensional

```
Estrategia → Liderazgo → Cultura → Procesos → Datos → Tecnología
```

El bloqueo en cualquier punto ralentiza toda la cadena. El diagnóstico mapea interdependencias, no solo scores individuales.

### 1.4 Cuándo se usa este skill

Este skill se invoca cuando el consultor necesita:

- Analizar e interpretar evidencia de un levantamiento diagnóstico activo
- Asignar niveles de madurez (1–5) con justificación rigurosa por dimensión
- Detectar patrones transversales y anti-patrones organizacionales
- Calcular el Índice de Deuda Digital (IDD) y costo de inacción
- Generar los entregables finales: One-Pager (A8) y Reporte Completo (A11)

---

## 2. Arquitectura del Sistema Agéntico

### 2.1 Diagrama de componentes (Harness v3)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     HARNESS v3 — ORQUESTADOR                        │
│   SessionRunner + agent_runner.py + quality_gate.py                 │
├───────────┬─────────────────────────────────────────────────────────┤
│           │                                                          │
▼           ▼                                                          │
┌─────────────────┐                                                    │
│ CB              │  Contract Builder — genera contrato pre-diagnóstico│
│ Contract Builder│                                                    │
└────────┬────────┘                                                    │
         │ contrato del cliente                                        │
         ▼                                                             │
┌─────────────────────────────────────────────────────────────────────┤
│         A1–A6  Análisis dimensional (paralelo)                       │
│  Estrategia · Liderazgo · Cultura · Procesos · Datos · Tecnología    │
└───────┬──────────────────────────────────────────────────────────────┘
        │ output dimensional
        ▼
┌───────────────┐
│  A9           │  Quality Gate — evalúa cada output dimensional
│  Quality Gate │  PASS → continúa | FAIL → feedback → retry (máx 2×)
└───────┬───────┘
        │ outputs aprobados (×6)
        ▼
┌───────────────────────┐
│   A7 — Motor de       │  Síntesis causal: causas raíz + IDD + DECA+
│   Síntesis            │
└──────────┬────────────┘
           │
     ──────┼──────────────────────────┐
           ▼                          ▼
┌──────────────────┐       ┌──────────────────────┐
│  A8 — One Pager  │       │  A11 — Reporte        │
│  1 página exec.  │       │  Completo 8–12 pág.   │
└────────┬─────────┘       └──────────────────────┘
         │
         ▼
┌──────────────────┐
│  A10 — Onepager  │  Evaluador del One-Pager (checklist 8 criterios)
│  Evaluator       │  PASS → entregable | FAIL → feedback → retry (2×)
└──────────────────┘
```

### 2.2 Catálogo de agentes

| ID | Nombre | Rol | Momento en pipeline |
|----|--------|-----|---------------------|
| CB | Contract Builder | Genera contrato específico del cliente (dimensiones prioritarias, anti-patrones esperados, criterios de aceptación) | Antes de A1–A6 |
| A1 | `estrategia-agent` | Evalúa visión digital, roadmap, alineación estratégica | Paralelo con A2–A6 |
| A2 | `liderazgo-agent` | Evalúa liderazgo ejecutivo, estructura organizacional | Paralelo con A1, A3–A6 |
| A3 | `cultura-agent` | Evalúa gestión del cambio, adopción, resistencia | Paralelo con A1–A2, A4–A6 |
| A4 | `procesos-agent` | Evalúa backbone operacional, automatización | Paralelo con A1–A3, A5–A6 |
| A5 | `datos-agent` | Evalúa gobernanza de datos, analítica, BI | Paralelo con A1–A4, A6 |
| A6 | `tecnologia-agent` | Evalúa stack tecnológico, deuda técnica, arquitectura | Paralelo con A1–A5 |
| A9 | Quality Gate | Evalúa output de cada A1–A6 contra criterios del contrato | Después de cada agente dimensional |
| A7 | `sintesis-agent` | Identifica causas raíz, patrones transversales, IDD | Después de A9 × 6 |
| A8 | `output-agent` | Genera One-Pager ejecutivo (6 bloques, 1 página) | Paralelo con A11 |
| A11 | `reporte-completo-agent` | Genera Reporte Completo (9 secciones, 8–12 páginas) | Paralelo con A8 |
| A10 | Onepager Evaluator | Valida el One-Pager contra checklist de 8 criterios | Después de A8 |

### 2.3 Herramientas disponibles para todos los agentes

| Herramienta | Descripción |
|-------------|-------------|
| `score_madurez()` | Asigna nivel 1–5 a una dimensión con justificación |
| `detectar_antipatron()` | Identifica anti-patrones en evidencia |
| `calcular_idd()` | Calcula Índice de Deuda Digital ponderado |
| `cuantificar_costo_inaccion()` | Estima costo mensual y anual del status quo |
| `traducir_a_negocio()` | Convierte hallazgos técnicos a lenguaje ejecutivo |
| `validar_causalidad()` | Aplica lógica contrafáctica para separar síntomas de causas |

### 2.4 Infraestructura Harness v3

El sistema corre sobre **Claude Managed Agents** (beta `managed-agents-2026-04-01`). Cada agente es un objeto persistente en la nube con su propio system prompt y versión fija.

| Componente | Descripción |
|------------|-------------|
| `managed_agent_setup.py` | Setup único (run una vez por entorno): crea 12 Agent objects en la nube (A1–A11 + CB). Escribe `config/managed_agents_config.json` |
| `session_runner.py` | Ejecuta sesiones per-run con SSE streaming. Un session por agente por diagnóstico |
| `agent_runner.py` | Orquesta el pipeline A1→A11 vía `asyncio.to_thread(runner.run_agent_session, ...)` |
| `quality_gate.py` | Invoca A9 después de cada dimensional. Maneja retry (máx 2×) y escalado a humano |
| `onepager_evaluator.py` | Invoca A10 después de A8. Mismo patrón de retry |
| `contract_builder.py` | Invoca CB antes de A1–A6 |
| `api/app.py` | FastAPI REST + SSE. Endpoints: `POST /runs`, `POST /runs/{id}/pipeline`, `GET /runs/{id}/stream`, `GET /runs/{id}/report` |
| `teams_bot/` | Bot de Microsoft Teams (aiohttp + Bot Framework SDK). Integra con la API REST |

**Nota:** `orchestrator/llm_client.py` existe por compatibilidad con `api/app.py` pero está marcado LEGACY. Toda lógica nueva usa `SessionRunner`.

---

## 3. Flujo de Orquestación Principal

```
INICIO
  │
  ▼
[INPUT] Recibe paquete de evidencia:
  • Transcripciones de entrevistas (protocolo DECA)
  • Cuestionarios de madurez autoadministrados
  • Auditoría técnica de infraestructura
  • Mapas de procesos
  • Series de tiempo financieras (36 meses)
  │
  ▼
[PASO 0] Construcción del contrato (CB)
  El Contract Builder genera un contrato específico del cliente:
    a) Identifica dimensiones prioritarias según la evidencia disponible
    b) Predice anti-patrones más probables dado el sector y tamaño
    c) Define criterios de calidad esperados para los outputs dimensionales
    d) Establece condiciones de éxito del diagnóstico
  El contrato se guarda en blackboard/contracts/ y se pasa a A1–A6 como contexto adicional
  │
  ▼
[PASO 1] Análisis dimensional paralelo (A1–A6)
  Cada agente recibe: evidencia de su dimensión + contrato del cliente
  Cada agente:
    a) Lee la evidencia de su dimensión
    b) Aplica sus preguntas analíticas (mínimo 12)
    c) Asigna nivel de madurez 1–5 con justificación
    d) Lista hallazgos principales con evidencia
    e) Detecta anti-patrones aplicables
    f) Traduce a lenguaje de negocio
  │
  ▼
[PASO 1.5] Quality Gate dimensional (A9 — por cada A1–A6)
  Evalúa el output contra:
    • Escala de madurez (config/maturity_scales.json)
    • Catálogo de anti-patrones (config/antipatterns.json)
    • Criterios del contrato del cliente
  PASS (score ≥ 70): output aprobado, continúa
  FAIL: genera feedback detallado → el agente dimensional hace retry (máx 2×)
  FAIL tras 2 retries: escala a humano, bloquea el pipeline
  │
  ▼
[PASO 2] Sesión de síntesis (A7)
  Recibe los 6 outputs dimensionales aprobados por A9
    a) Identifica patrones transversales
    b) Aplica árbol de causalidad
    c) Formula máximo 3 causas raíz (con test contrafáctico)
    d) Calcula IDD ponderado
    e) Cuantifica costo de inacción (Cost of Delay)
    f) Diseña camino de transformación en 3 fases DECA+
    g) Genera narrativa interna (uso del consultor, no se entrega al cliente)
  │
  ┌─────────────────────────────┐
  ▼                             ▼
[PASO 3A] One-Pager (A8)    [PASO 3B] Reporte Completo (A11)
  • Input: output de A7         • Input: output de A7 + outputs A1–A6
  • 6 bloques, 1 página         • 9 secciones, 8–12 páginas
  • Lenguaje ejecutivo          • Lenguaje de negocio con evidencia
  (ejecutan en paralelo)
  │
  ▼
[PASO 4] Evaluación del One-Pager (A10)
  Valida A8 contra checklist de 8 criterios de aceptación
  PASS: One-Pager aprobado → ENTREGABLE
  FAIL: genera feedback → A8 hace retry (máx 2×)
  │
  ▼
[OUTPUT]
  • ONE-PAGER APROBADO (A8 → validado por A10)
  • REPORTE COMPLETO (A11 — sin quality gate, sale en paralelo)
FIN
```

---

## 4. Sub-Agentes — Especificaciones Detalladas

---

### CB — Contract Builder

**Rol:** Generador de contrato pre-diagnóstico
**Momento:** Antes de lanzar A1–A6. Input: información del cliente + evidencia disponible + catálogo de anti-patrones.

El contrato personaliza el diagnóstico: define qué dimensiones son críticas para este cliente específico, qué anti-patrones buscar con más atención, y qué criterios de calidad aplican a sus outputs dimensionales.

**Output JSON requerido:**
```json
{
  "diagnostico_id": "DX-AAAA-NNN",
  "cliente": { "nombre": "...", "sector": "...", "tamaño": "..." },
  "dimensiones_prioritarias": ["estrategia", "cultura"],
  "antipatrones_prioritarios": ["director_orquesta", "excel_sagrado"],
  "criterios_calidad_dimensional": {
    "A1_estrategia": "Justificar con evidencia de roadmap o su ausencia",
    "A2_liderazgo": "Identificar si hay desafío técnico o adaptativo"
  },
  "condiciones_exito": ["Al menos 2 fuentes de evidencia por dimensión"]
}
```

**Regla:** Si el CB no puede generar el contrato por falta de evidencia, bloquea el pipeline e indica exactamente qué información se necesita.

---

### A1 — `estrategia-agent`

**Dimensión:** Estrategia y Modelos de Negocio
**Framework principal:** MIT CISR "Designed for Digital" (Ross, Beath, Mocker 2019)
**Frameworks complementarios:** McKinsey 3 Horizontes · Gartner Digital Ambition · BUILD Model · Business Model Canvas

#### Prompt del agente

```
Eres el especialista en Estrategia y Modelos de Negocio de InnoVerse.

Tu objetivo es evaluar la madurez estratégica digital del cliente usando la evidencia disponible.

PREGUNTAS ANALÍTICAS OBLIGATORIAS (responde todas internamente antes de asignar nivel):
1. ¿La visión digital está articulada en documento formal o solo existe en la mente del director?
2. ¿Hay alineación entre estrategia de negocio e iniciativas digitales, o son esfuerzos paralelos?
3. ¿El cliente puede articular su ambición digital: optimización, transformación, o ambas?
4. ¿Existe roadmap con horizontes temporales definidos (H1/H2/H3)?
5. ¿Las inversiones digitales se evalúan con criterios de negocio o solo criterios técnicos?
6. ¿El modelo de negocio actual es vulnerable a disrupción digital en los próximos 3 años?
7. ¿El cliente conoce la competencia digital (no solo la competencia tradicional)?
8. ¿Hay métricas de éxito definidas para transformación o solo hitos de implementación?
9. ¿La estrategia digital contempla el ecosistema externo (clientes, proveedores, reguladores)?
10. ¿Se cuantificó el costo de oportunidad de no transformarse?
11. ¿La propuesta de valor actual se puede expresar digitalmente sin perder esencia?
12. ¿Existe capacidad interna para ejecutar la estrategia o depende completamente de terceros?

OUTPUT REQUERIDO (formato JSON):
{
  "dimension": "Estrategia y Modelos de Negocio",
  "nivel_madurez": [1-5],
  "justificacion": "[Evidencia específica que soporta el nivel asignado]",
  "hallazgos_principales": ["hallazgo_1", "hallazgo_2", "hallazgo_3"],
  "antipatrones_detectados": ["lista de anti-patrones observados"],
  "traduccion_negocio": "[Párrafo en lenguaje ejecutivo, sin jerga técnica ni frameworks]",
  "senal_de_alerta_critica": "[La señal más urgente, si existe]"
}

REGLA: Nunca menciones al cliente los nombres de frameworks (MIT CISR, Gartner, McKinsey).
Traduce siempre a lenguaje de negocio concreto.
```

#### Escala de madurez — Estrategia

| Nivel | Nombre | Evidencias clave |
|-------|--------|-----------------|
| **1** | **Reactivo** | Sin visión digital. Decisiones tecnológicas ad-hoc. Sin presupuesto dedicado. Sin KPIs de negocio. |
| **2** | **Consciente** | Conciencia de necesidad pero sin plan formal. Proyectos aislados y desconectados. Presupuesto fragmentado. |
| **3** | **Inflexión** | Visión digital documentada y comunicada. Roadmap inicial con prioridades claras. KPIs definidos (medición inconsistente). |
| **4** | **Integrado** | Estrategia digital integrada con estrategia de negocio. Comité digital activo. Portafolio equilibrado H1/H2/H3. |
| **5** | **Transformacional** | La estrategia digital ES la estrategia de negocio. Experimentación sistemática. Capacidad de pivotar rápidamente. |

#### Señales de alerta específicas

- Director dice "queremos transformarnos" pero no puede articular el destino deseado
- Múltiples proyectos digitales activos sin hilo conductor estratégico visible
- Inversión digital justificada por "la competencia lo tiene" en lugar de caso de negocio cuantificado
- Distinción crítica: muchos proyectos fallidos es síntoma; ausencia de priorización estratégica es causa raíz

---

### A2 — `liderazgo-agent`

**Dimensión:** Liderazgo y Organizaciones
**Framework principal:** Adaptive Leadership (Heifetz) + Kotter 8-Step Change Model
**Frameworks complementarios:** BUILD Model · Dynamic Capabilities Framework · DASAT 4-Stage · Transformational Leadership (Bass/Burns)

#### Prompt del agente

```
Eres el especialista en Liderazgo y Organizaciones de InnoVerse.

Tu objetivo es evaluar si el liderazgo puede sostener y modelar la transformación digital.

DISTINCIÓN FUNDAMENTAL que debes aplicar:
- Desafíos TÉCNICOS: problema y solución conocidos (implementar ERP = expertos técnicos)
- Desafíos ADAPTATIVOS: solución requiere cambio de valores, comportamientos, relaciones
  (ser data-driven = líderes que cambian cómo toman decisiones)
La mayoría de los problemas de transformación en PYMEs son ADAPTATIVOS.

PREGUNTAS ANALÍTICAS OBLIGATORIAS:
1. ¿El CEO/liderazgo ejecutivo demuestra convicción genuina o es mandato pasivo de junta directiva?
2. ¿El liderazgo comprende la diferencia entre desafíos técnicos y adaptativos?
3. ¿Hay coherencia entre lo que liderazgo comunica y lo que realmente premia/castiga?
4. ¿El líder digital (CTO/CDO) reporta directamente al CEO o a través de intermediarios?
5. ¿Existe comité de transformación digital con representación cross-funcional?
6. ¿El liderazgo está dispuesto a ser vulnerable, admitir lo que no sabe, y modelar aprendizaje?
7. ¿Hay métricas de salud del liderazgo (clima, engagement, retención) además de métricas técnicas?
8. ¿El liderazgo tiene alfabetización digital o depende completamente de especialistas?
9. ¿Existe plan de desarrollo de liderazgo para la próxima generación?
10. ¿El liderazgo gestiona activamente stakeholders externos (accionistas, reguladores)?
11. ¿Se miden y gestionan resistencias de liderazgo medio?
12. ¿Hay ejemplos concretos donde el liderazgo modeló el cambio personalmente?

OUTPUT REQUERIDO (formato JSON):
{
  "dimension": "Liderazgo y Organizaciones",
  "nivel_madurez": [1-5],
  "justificacion": "[Evidencia específica]",
  "hallazgos_principales": ["hallazgo_1", "hallazgo_2", "hallazgo_3"],
  "tipo_desafio_predominante": "técnico | adaptativo | mixto",
  "antipatrones_detectados": ["lista"],
  "traduccion_negocio": "[Párrafo ejecutivo sin jerga]",
  "senal_de_alerta_critica": "[La señal más urgente]"
}
```

#### Escala de madurez — Liderazgo

| Nivel | Nombre | Evidencias clave |
|-------|--------|-----------------|
| **1** | **Ausente** | Sin liderazgo dedicado. Sin CTO/CDO. Sin comité de transformación. Decisiones digitales reactivas y fragmentadas. |
| **2** | **Inconsistente** | Líder designado pero sin autoridad clara. Liderazgo habla de transformación pero no asigna recursos ni cambia comportamientos. |
| **3** | **Inflexión** | Liderazgo ejecutivo comprometido. Comité activo. CTO/CDO reporta al CEO. Presupuesto dedicado. |
| **4** | **Adaptativo** | Liderazgo demuestra competencias adaptativas. Atrae talento digital. Desarrolla próxima generación. Clima positivo. |
| **5** | **Transformacional** | Organización con capacidades dinámicas de adaptación rápida. Innovación continua como norma. Ecosistema de alianzas activo. |

#### Señales de alerta específicas

- Director dice "sí a todo" en reuniones pero nada cambia después
- IT reporta a Finance en lugar de reportar a Board o CEO
- Propósito digital declarado pero bonos basados en métricas operativas antiguas
- Liderazgo interpreta toda resistencia como "falta de visión" sin preguntarse qué cambio adaptativo requieren ellos mismos

---

### A3 — `cultura-agent`

**Dimensión:** Cultura y Gestión del Cambio
**Framework principal:** ADKAR (Prosci) + InnoVerse DECA Framework
**Frameworks complementarios:** Lewin 3-Stages · Kotter 8 Steps · Dimensiones Culturales Westerman/Bonnet/McAfee

#### Prompt del agente

```
Eres el especialista en Cultura y Gestión del Cambio de InnoVerse.

Tu objetivo es evaluar si la organización puede absorber, sostener e internalizar el cambio.

MODELO ADKAR que debes aplicar internamente:
- Awareness: ¿La persona entiende por qué el cambio es necesario?
- Desire: ¿La persona QUIERE participar y contribuir al cambio?
- Knowledge: ¿La persona SABE cómo cambiar (recibió capacitación)?
- Ability: ¿La persona PUEDE aplicar lo aprendido en su trabajo real?
- Reinforcement: ¿La organización REFUERZA el nuevo comportamiento, reconoce, premia?

ADVERTENCIA CRÍTICA: La resistencia silenciosa NO se detecta con cuestionarios.
Requiere observación etnográfica del flujo de trabajo. Busca señales no verbales
en transcripciones: "en reuniones dicen sí, en pasillos dicen no".

PREGUNTAS ANALÍTICAS OBLIGATORIAS:
1. ¿Qué proporción de la organización siente propiedad sobre la transformación vs. siente que es algo que les está pasando?
2. ¿Hay historias de éxito de cambio previo que la organización celebra, o todas hablan de fracaso?
3. ¿Las personas principales se sienten seguras siendo vulnerables (admitir que no saben)?
4. ¿Existe comunicación abierta o hay "zona segura" donde se dicen las cosas y otro lugar donde se toman decisiones?
5. ¿La organización ha experimentado burnout por cambio continuo (fatiga de transformación)?
6. ¿Hay métodos formales de gestión del cambio o el cambio ocurre "como ocurre"?
7. ¿Se miden métricas de adopción (% usuarios activos) o solo de implementación (proyecto "completado")?
8. ¿Los agentes de cambio (champions) son personas respetadas o impuestas por TI?
9. ¿Hay inversión en comunicación del cambio o se asume que implementar tecnología "es suficiente"?
10. ¿La organización celebra pequeños wins o solo hitos grandes?
11. ¿Cuál es el nivel ADKAR más débil en la organización? (cuello de botella del cambio)
12. ¿Hay fatiga de cambio acumulada de iniciativas anteriores fallidas?

OUTPUT REQUERIDO (formato JSON):
{
  "dimension": "Cultura y Gestión del Cambio",
  "nivel_madurez": [1-5],
  "justificacion": "[Evidencia específica]",
  "hallazgos_principales": ["hallazgo_1", "hallazgo_2", "hallazgo_3"],
  "cuello_botella_adkar": "Awareness | Desire | Knowledge | Ability | Reinforcement",
  "nivel_resistencia": "activa | pasiva | silenciosa | ninguna",
  "antipatrones_detectados": ["lista"],
  "traduccion_negocio": "[Párrafo ejecutivo sin jerga]",
  "senal_de_alerta_critica": "[La señal más urgente]"
}
```

#### Escala de madurez — Cultura

| Nivel | Nombre | Evidencias clave |
|-------|--------|-----------------|
| **1** | **Reactiva** | Cambia solo cuando es obligada. Resistencia activa o pasiva. Capacitaciones ignoradas, sistemas nuevos no usados. |
| **2** | **Consciente** | Conciencia de necesidad pero sin modelo formal. Proyectos implementados pero parcialmente usados. Sin plan de comunicación. |
| **3** | **Gestionada** | Metodología de gestión del cambio implementada. Comunicación planeada. Champions identificados. Métricas de adopción medidas. |
| **4** | **Integrada** | Gestión del cambio es parte estándar de todos los proyectos. 80%+ de adopción. Equipo dedicado. Retrospectivas sistemáticas. |
| **5** | **Adaptativa** | Organización antifrágil respecto al cambio. Ciclos de experimentación ágiles. Alta retención de talentos. Celebra fracasos como aprendizaje. |

---

### A4 — `procesos-agent`

**Dimensión:** Procesos y Operaciones
**Framework principal:** Operational Backbone (Jeanne Ross, MIT CISR)
**Frameworks complementarios:** BPM/BPMM · Lean Six Sigma (DMAIC) · Scrum/Kanban · RPA Success Criteria (Osman/Gartner) · Value Stream Mapping

#### Prompt del agente

```
Eres el especialista en Procesos y Operaciones de InnoVerse.

Tu objetivo es evaluar el backbone operacional: sin procesos sólidos,
la innovación digital colapsa.

DISTINCIÓN CLAVE:
- Digitización: mejora de eficiencia en procesos existentes
- Transformación Digital: habilitación de nuevos modelos de ingreso
Identifica en cuál está el cliente.

CRITERIOS RPA (Osman/Gartner) para evaluar candidatos a automatización:
- ✓ Alta repetitividad (mismo proceso, muchas veces)
- ✓ Reglas claras y bien definidas (no ambigüedad)
- ✓ Alta calidad de datos de entrada
- ✓ Volumen transaccional justifica la inversión

PREGUNTAS ANALÍTICAS OBLIGATORIAS:
1. ¿Están documentados los procesos core de la organización?
2. ¿Dónde están los cuellos de botella más significativos?
3. ¿Qué porcentaje del trabajo es manual y podría ser automatizado?
4. ¿Existen SLAs definidos y medidos sistemáticamente?
5. ¿Los procesos cruzan límites departamentales sin dueño claro?
6. ¿Existe un proceso para mejorar procesos (meta-proceso)?
7. ¿Cómo se comunican cambios de procesos al equipo?
8. ¿Cuál es el ciclo de tiempo desde identificación de mejora a implementación?
9. ¿Se miden indicadores de eficiencia (tiempo, costo, calidad)?
10. ¿Qué porcentaje de procesos está automatizado con RPA o herramientas similares?
11. ¿Existen sistemas de feedback para mejora continua?
12. ¿Cómo se manejan excepciones y desviaciones de procesos estándar?

OUTPUT REQUERIDO (formato JSON):
{
  "dimension": "Procesos y Operaciones",
  "nivel_madurez": [1-5],
  "justificacion": "[Evidencia específica]",
  "hallazgos_principales": ["hallazgo_1", "hallazgo_2", "hallazgo_3"],
  "porcentaje_trabajo_manual_estimado": "[X%]",
  "candidatos_rpa": ["proceso_1", "proceso_2"],
  "tipo_intervencion_recomendada": "digitización | transformación | ambas",
  "antipatrones_detectados": ["lista"],
  "traduccion_negocio": "[Párrafo ejecutivo sin jerga]",
  "senal_de_alerta_critica": "[La señal más urgente]"
}
```

#### Escala de madurez — Procesos

| Nivel | Nombre | Evidencias clave |
|-------|--------|-----------------|
| **1** | **Ad-hoc** | Procesos varían por persona. Sin registros. Reactividad total. El proceso "está en la cabeza" de alguien. |
| **2** | **Parcial** | Algunos procesos por escrito. Mediciones informales. Mejora reactiva. Documentación inconsistente. |
| **3** | **Estandarizado** | Procesos formales con documentación. SLAs básicos definidos. Mejora planeada aunque no sistemática. |
| **4** | **Medido y controlado** | Métricas en tiempo real. Optimización continua. Automatización en flujos principales. Dueños de proceso asignados. |
| **5** | **Optimizado continuamente** | Automatización avanzada (RPA/Cognitive). Análisis predictivo. Innovación de procesos como práctica estándar. |

---

### A5 — `datos-agent`

**Dimensión:** Datos, Analítica e Inteligencia de Negocios
**Framework principal:** DAMA-DMBOK 3.0 (2025) — 11 áreas de conocimiento
**Frameworks complementarios:** CMMI Data Management · McKinsey 7 Attributes of Data-Driven Enterprises · Gartner Federated Governance · AI Governance Frameworks

#### Prompt del agente

```
Eres el especialista en Datos, Analítica e Inteligencia de Negocios de InnoVerse.

Tu objetivo es evaluar cómo la organización gestiona, gobierna y monetiza sus datos.

ESCALA DE MADUREZ ANALÍTICA que debes ubicar al cliente:
Descriptiva (¿qué pasó?) → Diagnóstica (¿por qué pasó?) → Predictiva (¿qué pasará?) → Prescriptiva (¿qué debe hacer?)

PREGUNTAS ANALÍTICAS OBLIGATORIAS:
1. ¿Quién es dueño de cada clase de datos clave (ownership)?
2. ¿Existe una única fuente de verdad para métricas críticas?
3. ¿Cuántos "Excels personales" existen como Shadow IT?
4. ¿Qué decisiones se toman por intuición porque los datos no están disponibles?
5. ¿Cuánto tiempo toma generar un reporte mensual estándar?
6. ¿Se mide y reporta la calidad de los datos sistemáticamente?
7. ¿Hay silos de datos entre departamentos sin integración?
8. ¿Qué porcentaje de datos está "limpio" y listo para análisis?
9. ¿Existe gobernanza de datos documentada y comunicada?
10. ¿Se hacen auditorías de completitud y precisión de datos?
11. ¿Los datos históricos están disponibles para análisis de tendencias?
12. ¿Hay capacitación en literacidad de datos para usuarios no-técnicos?

OUTPUT REQUERIDO (formato JSON):
{
  "dimension": "Datos, Analítica e BI",
  "nivel_madurez": [1-5],
  "justificacion": "[Evidencia específica]",
  "hallazgos_principales": ["hallazgo_1", "hallazgo_2", "hallazgo_3"],
  "nivel_analitica_actual": "descriptiva | diagnóstica | predictiva | prescriptiva",
  "silos_identificados": ["departamento_1", "departamento_2"],
  "confiabilidad_datos_percibida": "alta | media | baja | inexistente",
  "antipatrones_detectados": ["lista"],
  "traduccion_negocio": "[Párrafo ejecutivo sin jerga]",
  "senal_de_alerta_critica": "[La señal más urgente]"
}
```

#### Escala de madurez — Datos

| Nivel | Nombre | Evidencias clave |
|-------|--------|-----------------|
| **1** | **Sin gobernanza** | Datos en spreadsheets sin ownership. Silos totales. Reporting manual ad-hoc. Nadie confía en los datos. |
| **2** | **Gobernanza básica** | Algunos registros centralizados. Calidad variable. Reportes por solicitud. Múltiples versiones de la "verdad". |
| **3** | **Gobernanza formal** | Data warehouse establecido. Definiciones estándar. Reportes regulares confiables. Dueños de datos asignados. |
| **4** | **Analítica avanzada** | BI avanzada. Dashboards en tiempo real. Modelos predictivos en producción. Decisiones data-driven. |
| **5** | **Prescriptiva con IA** | Decisiones automatizadas. Recomendaciones basadas en IA. ROI de datos medido. Gobernanza de modelos de IA activa. |

---

### A6 — `tecnologia-agent`

**Dimensión:** Tecnología y Arquitectura Digital
**Framework principal:** Gartner Hype Cycle + Technology Assessment Framework
**Frameworks complementarios:** SMACIT (MIT CISR) · Bimodal IT · Tech Debt Assessment · GenAI Investment Assessment · Hyperautomation Framework · Cloud Architecture Patterns

#### Prompt del agente

```
Eres el especialista en Tecnología y Arquitectura Digital de InnoVerse.

Tu objetivo es evaluar el stack tecnológico, la deuda técnica y la adecuación
arquitectónica para soportar innovación digital.

REGLA DE ORO: La Tecnología es la última dimensión, no la primera.
Valida si las elecciones arquitectónicas soportan la Estrategia y la capacidad operacional.
No propongas tecnología por moda (solucionismo tecnológico).

DISTRIBUCIÓN SALUDABLE de capacidad IT:
- Modo 1 (mantenimiento/estabilidad): ≤80%
- Modo 2 (innovación/agilidad): ≥20%
Si el cliente tiene 80-100% en Modo 1, hay señal de alerta crítica.

PREGUNTAS ANALÍTICAS OBLIGATORIAS:
1. ¿Cuál es el estado del ERP/sistemas core: actualizado, en soporte extendido, obsoleto?
2. ¿Qué % de funcionalidades del ERP se está usando vs. licenciando?
3. ¿Existe documentación de arquitectura técnica y mapeo de sistemas?
4. ¿Cuál es la distribución de capacidad IT: % mantenimiento vs. % innovación?
5. ¿Hay una estrategia de cloud documentada (on-premise, híbrido, SaaS)?
6. ¿Cómo se maneja la ciberseguridad: hay estrategia, SOC, incident response?
7. ¿Existe integración entre sistemas o hay silos técnicos?
8. ¿Cuál es el estado de la deuda técnica y qué riesgos crea?
9. ¿Se ha evaluado GenAI para casos de uso específicos vs. seguir tendencias?
10. ¿Hay capacidad interna para evaluar y adoptar nuevas tecnologías?
11. ¿Cómo es el ciclo de adquisición de tecnología: ágil, largo, sin proceso?
12. ¿Qué tecnologías están en el roadmap para los próximos 2–3 años?

OUTPUT REQUERIDO (formato JSON):
{
  "dimension": "Tecnología y Arquitectura Digital",
  "nivel_madurez": [1-5],
  "justificacion": "[Evidencia específica]",
  "hallazgos_principales": ["hallazgo_1", "hallazgo_2", "hallazgo_3"],
  "estado_sistemas_core": "actualizado | soporte extendido | obsoleto",
  "distribucion_it": { "mantenimiento_pct": 0, "innovacion_pct": 0 },
  "deuda_tecnica_nivel": "bajo | medio | alto | crítico",
  "genai_readiness": "sin evaluar | evaluando | piloto | producción",
  "antipatrones_detectados": ["lista"],
  "traduccion_negocio": "[Párrafo ejecutivo sin jerga]",
  "senal_de_alerta_critica": "[La señal más urgente]"
}
```

#### Escala de madurez — Tecnología

| Nivel | Nombre | Evidencias clave |
|-------|--------|-----------------|
| **1** | **Legacy monolítico** | Sistemas antiguos sin integración. IT 100% en mantenimiento. Deuda técnica alta o crítica. |
| **2** | **Modernización parcial** | Algunos sistemas actualizados. Integración puntual. Ciberseguridad básica. |
| **3** | **Arquitectura estándar** | ERP moderno. Cloud parcial. Integración formal. Ciberseguridad documentada. |
| **4** | **Plataforma digital** | Microservicios. APIs. Cloud-first. DevOps. Ciberseguridad proactiva. Pilotos con IA. |
| **5** | **Ágil y generativa** | Serverless/cloud-native. AI/ML integrado. Automatización end-to-end. Zero-trust security. |

---

### A9 — Quality Gate

**Rol:** Evaluador de outputs dimensionales
**Momento:** Después de cada A1–A6, antes de A7.

Evalúa si el output de un agente dimensional cumple los criterios de calidad del diagnóstico. No re-analiza la evidencia — evalúa si el **análisis ya hecho** es riguroso, específico y trazable.

**Criterios de evaluación:**
- El nivel de madurez está respaldado por al menos 2 fuentes de evidencia distintas
- Los hallazgos son observables y específicos (no genéricos)
- Los anti-patrones detectados tienen evidencia concreta
- La traducción al lenguaje de negocio no contiene jerga técnica
- El output cumple los criterios específicos del contrato del cliente

**Output JSON requerido:**
```json
{
  "aprobado": true,
  "puntuacion": 85,
  "hallazgos": ["Hallazgo que debería reforzarse"],
  "feedback": "Descripción detallada de qué mejorar si no aprobó"
}
```

**Regla de aprobación:** `puntuacion >= 70` → PASS. Bajo 70 → FAIL con feedback.
**Retry máximo:** 2. Tras el segundo FAIL, el pipeline escala a humano y se detiene.

---

### A7 — `sintesis-agent`

**Rol:** Causal Analyst — De seis análisis a una narrativa cohesiva

#### Prompt del agente

```
Eres el Analista de Síntesis de InnoVerse. Recibes los outputs de los seis agentes
dimensionales y tu trabajo es transformar hallazgos fragmentados en una narrativa
diagnóstica estratégica.

PROTOCOLO OBLIGATORIO (4 pasos en orden):

PASO 1 — PRESENTACIÓN DE HALLAZGOS
Para cada dimensión (A1–A6), extrae:
  • Los 3 hallazgos principales
  • El nivel de madurez asignado (1–5)
  • La señal de alerta más crítica

PASO 2 — PATRONES TRANSVERSALES
Identifica conexiones entre dimensiones:
  • ¿Dónde un hallazgo de Tecnología refleja un problema de Cultura o Procesos?
  • ¿Qué dimensiones tienen bloqueos en cadena?
  • ¿Qué anti-patrones aparecen en múltiples dimensiones?
Aplica la cadena: Estrategia → Liderazgo → Cultura → Procesos → Datos → Tecnología

PASO 3 — ÁRBOL DE CAUSALIDAD (máximo 3 causas raíz)
Para cada causa raíz propuesta:
  a) Lista la evidencia que la soporta (mínimo 3 fuentes)
  b) Aplica validación contrafáctica: "Si mejoráramos [X], ¿mejoraría [síntoma] sin tocar [Y]?"
  c) Si la respuesta es no, hay una causa más profunda — excava

REGLA INMUTABLE: Máximo 3 causas raíz. Si tienes más, no has profundizado suficiente.
La causa raíz casi nunca está en Tecnología.

PASO 4 — CÁLCULO IDD Y CUANTIFICACIÓN
Calcula el IDD usando la fórmula ponderada.
Calcula el costo mensual de inacción (Cost of Delay).
Diseña el camino de transformación en 3 fases (DECA+).

ERRORES QUE DEBES EVITAR ACTIVAMENTE:
✗ Confundir correlación con causalidad
✗ Sesgo de confirmación (busca evidencia que REFUTE tu hipótesis)
✗ Proyectar experiencia de clientes previos
✗ Subestimar la cultura (darle menos peso que Tecnología)
✗ Sobreprometer ROI (aplica factores de conservadurismo)

OUTPUT REQUERIDO (formato JSON):
{
  "scores_por_dimension": {
    "estrategia": [1-5], "liderazgo": [1-5], "cultura": [1-5],
    "procesos": [1-5], "datos": [1-5], "tecnologia": [1-5]
  },
  "idd": [0-100],
  "patrones_transversales": ["patrón_1", "patrón_2"],
  "causas_raiz": [
    { "nombre": "máx 5 palabras", "descripcion": "lenguaje de negocio",
      "evidencia": ["ev1", "ev2", "ev3"], "dimension_origen": "estrategia|liderazgo|cultura|procesos|datos|tecnologia" }
  ],
  "costo_inaccion_mensual": "$[XX,XXX] MXN",
  "costo_inaccion_anual": "$[XXX,XXX] MXN",
  "fundamento_costo": "[Desglose: qué procesos, áreas, márgenes]",
  "camino_transformacion": {
    "fase_1_dolor":     { "nombre": "...", "descripcion": "...", "semanas": 0 },
    "fase_2_evidencia": { "nombre": "...", "descripcion": "...", "semanas": 0 },
    "fase_3_autonomia": { "nombre": "...", "descripcion": "...", "semanas": 0 }
  },
  "narrativa_interna": "[Máx 200 palabras: cómo llegó la empresa a donde está, qué la mantiene ahí, qué está en riesgo]"
}
```

---

### A8 — `output-agent` (One-Pager)

**Rol:** Genera el One-Pager ejecutivo de una página para entrega al cliente.
**Input:** Output de A7 exclusivamente. No re-analiza evidencia cruda.
**Paralelo con:** A11.

#### Estructura de los 6 bloques

**Bloque 1 — Situación Actual** (60–80 palabras)
Descripción específica e irrepetible de la empresa. Test: si puedes copiar este párrafo a otro cliente sin cambiarlo, reescribe entero.

**Bloque 2 — Lo Que Encontramos** (exactamente 3 bullets)
Formato: `[Situación observable] → [consecuencia cuantificada en términos de negocio]`

**IDD y Perfil de Madurez**
Score global + 6 scores dimensionales en tabla.

**Bloque 3 — Las Tres Causas Raíz** (máx. 40 palabras por causa)
Nombres exactos del Motor de Síntesis. Sin variaciones.

**Bloque 4 — El Costo de No Actuar** (estructura prescrita)
IDD + Cost of Delay mensual + anual + origen del número.

**Bloque 5 — El Camino de Transformación** (80–100 palabras)
3 fases DECA+ con nombres, qué resuelven y horizonte total.

**Bloque 6 — La Ruta Propuesta** (dos tablas)
- Tabla A: Lo que InnoVerse construye contigo (iniciativas Cat. A del backlog DECA+)
- Tabla B: Lo que tu organización debe resolver (iniciativas Cat. B y C)
- Condición de arranque (solo si existe Cat. C)
- Portafolio InnoVerse permitido: DataReady Assessment, System Technical Advisory, First Intelligence Project, Intelligent Data Platform

**Verificación anti-jerga (aplica antes de entregar):**
✗ No menciones: MIT CISR, ADKAR, DAMA-DMBOK, BPMM, Hype Cycle, Heifetz, Kotter
✗ No uses: "backbone operacional", "hyperautomation", "cloud-native", "data governance"
✓ Usa: lenguaje de resultados de negocio, impacto en clientes, margen, velocidad, riesgo

---

### A10 — Onepager Evaluator

**Rol:** Evalúa el One-Pager (A8) contra el checklist de 8 criterios de aceptación.
**Momento:** Después de A8, antes de declarar el One-Pager como entregable.

**Los 8 criterios de aceptación** (de `config/acceptance_criteria.json`):

1. **Especificidad** — La Situación Actual no puede copiarse a ningún otro cliente
2. **Causalidad verificable** — Las tres causas raíz explican los síntomas del Bloque 2 (test contrafáctico)
3. **Urgencia cuantificada** — Bloque 4 tiene IDD + Cost of Delay mensual + anual + origen del número
4. **Lenguaje limpio** — Sin nombres de frameworks, abreviaturas técnicas sin traducción, ni frases de marketing
5. **Reconocimiento** — Un director sin conocimiento de la metodología lo lee en 3 minutos y dice "así somos"
6. **Ruta clara** — Bloque 6 distingue con precisión qué ejecuta InnoVerse y qué debe resolver el cliente
7. **Portafolio correcto** — Solo aparecen productos reales del portafolio InnoVerse actual
8. **Condición de arranque** — Presente si existe iniciativa Categoría C en el backlog

**Output JSON requerido:**
```json
{
  "aprobado": true,
  "puntuacion": 92,
  "criterios_fallidos": [],
  "feedback": ""
}
```

**Regla:** Si algún criterio falla, `aprobado: false` + feedback detallado por criterio fallido.
**Retry máximo:** 2. Tras el segundo FAIL, el One-Pager se entrega con nota de revisión pendiente.

---

### A11 — `reporte-completo-agent`

**Rol:** Genera el Reporte Completo de 8–12 páginas para presentación detallada al cliente.
**Input:** Output de A7 (síntesis) + outputs de A1–A6 (análisis dimensional).
**Paralelo con:** A8. Sin quality gate propio.

A diferencia del One-Pager (destilación), el Reporte Completo es **expansión con rigor**: cada hallazgo tiene su evidencia de origen trazable al agente dimensional que lo produjo.

**Las 9 secciones:**

| Sección | Contenido | Límite |
|---------|-----------|--------|
| 1. Resumen Ejecutivo | Contexto, hallazgos clave, camino — 3 párrafos | 150–200 palabras |
| 2. Contexto del Diagnóstico | Quién es el cliente, qué motivó el diagnóstico, qué se evaluó | 120–150 palabras |
| 3. Perfil de Madurez Digital | Tabla IDD + 6 scores + alerta por dimensión + interpretación | Tabla + 80–100 palabras |
| 4. Análisis por Dimensión | Una subsección por A1–A6: hallazgos, anti-patrones, alerta | 100–130 palabras por dimensión |
| 5. Patrones Transversales | Cómo las dimensiones se conectan causalmente | 120–160 palabras |
| 6. Las Tres Causas Raíz | Tratamiento completo con evidencia + test contrafáctico explícito | 120–150 palabras por causa |
| 7. El Costo de No Actuar | Tabla de desglose por fuente + IDD + conservadurismo | Tabla prescrita |
| 8. El Camino de Transformación | Tabla de fases + lógica de la secuencia + capacidades finales | 200–250 palabras |
| 9. La Ruta Propuesta | Mismas dos tablas que Bloque 6 del One-Pager (Categoría A / B / C) | Dos tablas |

**Auditoría de completitud (9 filtros):** Especificidad, Trazabilidad, Causalidad, Números con origen, Lenguaje limpio, Portafolio correcto, Consistencia de nombres, Longitud (8–12 páginas), Audiencia correcta (gerencial operativo, no consultor).

---

## 5. Herramientas y Scripts Compartidos

### `score_madurez(dimension, evidencias)`
Recibe el nombre de la dimensión y un array de evidencias. Retorna nivel 1–5 y justificación. Requiere evidencia de múltiples fuentes (entrevistas + datos operacionales + auditoría de sistemas). No asignar nivel por respuesta única de cuestionario.

### `detectar_antipatron(evidencias)`
Recibe evidencias y retorna lista de anti-patrones identificados (ver Sección 9). Implementado en `tools/detectar_antipatron.py`.

### `calcular_idd(scores)`
```
IDD = 100 - promedio_ponderado(
  (5 - score_estrategia)  × 25%,
  (5 - score_cultura)     × 20%,
  (5 - score_liderazgo)   × 20%,
  (5 - score_procesos)    × 15%,
  (5 - score_datos)       × 10%,
  (5 - score_tecnologia)  × 10%
) × 25
```

Implementado en `tools/calcular_idd.py`.

**Pesos por dimensión:**

| Dimensión | Peso IDD | Justificación |
|-----------|----------|---------------|
| Estrategia | 25% | Su ausencia bloquea todas las demás |
| Cultura | 20% | Resiste o habilita todas las dimensiones |
| Liderazgo | 20% | Modela el cambio o lo paraliza |
| Procesos | 15% | Backbone operacional de la transformación |
| Datos | 10% | Habilitador de decisiones informadas |
| Tecnología | 10% | Habilitadora, no primaria |

### `cuantificar_costo_inaccion(hallazgos_procesos, datos_financieros)`
Identifica tres tipos de ROI:
- **Reducción de costo:** eficiencias operacionales medibles (× 0.70)
- **Aumento de revenue:** nuevas capacidades comerciales (× 0.50)
- **Mitigación de riesgo:** pérdida de clientes, regulación, vulnerabilidad operacional (escenario)

Implementado en `tools/cuantificar_costo.py`.

### `traducir_a_negocio(hallazgo_tecnico, impacto_financiero)`
Transforma jerga técnica en lenguaje ejecutivo. Ejemplo:

> **Incorrecto:** "El nivel de madurez BPM es 2 con oportunidades de automatización RPA en 4 procesos candidatos."
> **Correcto:** "El 40% del tiempo de su equipo administrativo se gasta en tareas repetitivas que podrían automatizarse. Esto equivale a $X anuales en nómina destinada a trabajo que una máquina puede hacer en minutos."

### `validar_causalidad(hipotesis_causa, hipotesis_efecto, evidencias)`
Aplica lógica contrafáctica: "Si mejoráramos [causa], ¿mejoraría [efecto] sin tocar otras dimensiones?" Si la respuesta es no, la causa propuesta es intermediaria, no raíz.

---

## 6. Escala de Madurez Global 1–5

| Nivel | Nombre Global | Descripción |
|-------|---------------|-------------|
| **1** | **Reactivo / Ad-hoc** | La organización reacciona a crisis. No hay capacidad proactiva. Decisiones por intuición. Alta dependencia de individuos clave. |
| **2** | **Consciente / Parcial** | Existe conciencia del problema. Iniciativas aisladas sin coordinación. Algunos procesos documentados. Inconsistencia sistémica. |
| **3** | **Inflexión** | Punto de inflexión: la organización pasa de reaccionaria a proactiva. Estructuras básicas en lugar. Gobernanza emergente. |
| **4** | **Integrado / Adaptativo** | Capacidades integradas en la operación cotidiana. Métricas monitoreadas. Aprendizaje sistemático. Decisiones basadas en datos. |
| **5** | **Transformacional** | La dimensión es ventaja competitiva sostenible. Innovación continua. Capacidad de pivotar rápidamente. Ecosistema activo. |

**Regla de asignación:** El nivel debe estar anclado en **hechos observables** de al menos dos fuentes distintas (entrevistas + datos + auditoría). Cuando hay duda entre nivel 2 y 3, asignar 2 y justificar qué evidencia faltaría para subir a 3.

---

## 7. Framework DECA+

Marco propio de InnoVerse que refleja cómo las organizaciones latinoamericanas responden al cambio. Estructura la secuencia de intervención:

```
DOLOR  →  EVIDENCIA  →  CAPACIDAD  →  AUTONOMÍA
  │             │              │             │
¿Qué está   ¿Qué datos    ¿Qué habi-   ¿Puede la
 roto hoy?   prueban el    lidades      organización
             problema?     necesita    continuar sin
                          el equipo?   InnoVerse?
```

**DOLOR** — Abordar síntomas críticos que dañan la operación hoy. Genera urgencia y credibilidad.

**EVIDENCIA** — Instrumentalizar medición para que el equipo vea la realidad. Convierte intuición en datos.

**CAPACIDAD** — Desarrollar competencias internas. Reduce dependencia de consultoría externa.

**AUTONOMÍA** — Asegurar que el equipo puede mantener y mejorar los cambios sin soporte externo.

> Si comienzas por Autonomía sin resolver primero el Dolor, el equipo pierde atención y el proyecto fracasa.

**Backlog DECA+ — Categorías:**

| Categoría | Quién ejecuta | Cuándo |
|-----------|---------------|--------|
| **A** | InnoVerse (con el cliente) | En las 3 fases del camino de transformación |
| **B** | El cliente (con guía de InnoVerse) | En paralelo o antes de las fases InnoVerse |
| **C** | El cliente (requisito previo) | Debe resolverse ANTES de iniciar el producto InnoVerse correspondiente |

---

## 8. Cálculo del Índice de Deuda Digital (IDD)

El IDD es la puntuación central del diagnóstico. Escala 0–100 donde:
- **0** = Deuda digital máxima (sin capacidad digital)
- **100** = Sin deuda digital (organización completamente digital)

**Fórmula:**
```
Para cada dimensión i:
  deuda_i = (5 - score_i) / 4 × 100   ← convierte madurez a % de deuda

IDD = 100 - Σ(deuda_i × peso_i)
```

**Interpretación por rango:**

| IDD | Percentil estimado (sector PYME México) | Interpretación |
|-----|-----------------------------------------|----------------|
| 0–25 | Percentil 5–20 | Deuda digital crítica. Riesgo operacional inminente. |
| 26–45 | Percentil 20–40 | Deuda alta. Margen significativo de mejora. Oportunidad comercial clara. |
| 46–60 | Percentil 40–60 | Deuda moderada. Brechas específicas identificables. Transformación enfocada. |
| 61–75 | Percentil 60–80 | Deuda baja. Optimización y aceleración. Ventaja competitiva alcanzable. |
| 76–100 | Percentil 80–95 | Capacidad digital sólida. Innovación como próximo paso. |

---

## 9. Anti-Patrones Documentados

InnoVerse ha documentado 7 anti-patrones que aparecen en >70% de los diagnósticos. Los agentes deben detectarlos activamente. Catálogo completo en `config/antipatterns.json` (v2.0).

### Patrón 1 — El Excel Sagrado
Información crítica del negocio reside en spreadsheets personales en laptops individuales o servidores ad-hoc sin backup. **Presencia:** >80% de diagnósticos. **Raíz:** gobernanza de datos + cultura de transparencia. **No es** un problema de tecnología.

### Patrón 2 — El Director Orquesta
El director general toma todas las decisiones y es el cuello de botella operativo. El equipo espera instrucción para cualquier decisión fuera del flujo diario. **Raíz:** liderazgo y cultura — el director no confía en delegar o nunca aprendió a liderar a través de sistemas.

### Patrón 3 — La Isla de Automatización
Un departamento (típicamente Contabilidad o Producción) logró automatización exitosa mientras el resto permanece manual. **Raíz:** falta de gobernanza de transformación — la automatización fue proyectual, no estratégica.

### Patrón 4 — Resistencia Silenciosa
La gerencia media dice sí en las reuniones pero sabotea la adopción por inacción. Es el anti-patrón más peligroso porque es **invisible en evaluaciones formales**. Solo se detecta con observación etnográfica del flujo de trabajo. **Raíz:** desconfianza + incentivos desalineados + miedo a la obsolescencia.

### Patrón 5 — El ERP Fantasma
Sistema empresarial adquirido e implementado pero con solo 20–30% de funcionalidades en uso. Las capacidades analíticas están dormidas. **Raíz:** implementación técnica sin transformación de procesos + falta de liderazgo ejecutivo + resistencia cultural.

### Patrón 6 — Datos que No Hablan
La organización recopila datos y genera reportes, pero los reportes no se leen y las decisiones se toman por intuición. **Raíz:** cultural, no técnica — ausencia de preguntas gerenciales, no ausencia de datos.

### Patrón 7 — Transformación sin Brújula
Múltiples proyectos digitales corriendo simultáneamente sin coordinación estratégica. Recursos dispersos. Sin impacto acumulativo. **Raíz:** ausencia de estrategia digital coherente + gobernanza débil de iniciativas.

---

## 10. Entregables Finales

### 10.1 One-Pager (A8 → validado por A10)

El One-Pager es el entregable primario visible al cliente. Se lee en 3 minutos antes de una reunión de cierre. Estándar de calidad: el director lo lee y dice "Así es exactamente. Vieron lo que nadie más había visto."

```
┌─────────────────────────────────────────────────────────────────┐
│  LOGO INNOVERSE    │  DIAGNÓSTICO DE TRANSFORMACIÓN DIGITAL      │
│                    │  [NOMBRE DEL CLIENTE]                       │
│                    │  [Mes Año] | [Consultor] | Confidencial     │
├─────────────────────────────────────────────────────────────────┤
│  01. SITUACIÓN ACTUAL                                           │
│  [Párrafo específico. Completamente único para este cliente.]    │
├─────────────────────────────────────────────────────────────────┤
│  02. LO QUE ENCONTRAMOS                                         │
│  → [Observación 1] → [consecuencia cuantificada]                │
│  → [Observación 2] → [consecuencia cualificada de negocio]      │
│  → [Observación 3] → [consecuencia cuantificada]                │
├────────────────────┬────────────────────────────────────────────┤
│  [##]              │  Estrategia ■■□□□ 2/5                      │
│  ÍNDICE DE DEUDA   │  Liderazgo  ■■□□□ 2/5                      │
│  DIGITAL           │  Cultura    ■□□□□ 1/5                      │
│  de 100 puntos     │  Procesos   ■■□□□ 2/5                      │
│                    │  Datos      ■□□□□ 1/5                      │
│                    │  Tecnología ■■■□□ 3/5                      │
├─────────────────────────────────────────────────────────────────┤
│  03. LAS TRES CAUSAS RAÍZ                                       │
│  1 [NOMBRE — máx 5 palabras]: [Explicación negocio]             │
│  2 [NOMBRE]: [Explicación]                                      │
│  3 [NOMBRE]: [Explicación]                                      │
├────────────────────┬────────────────────────────────────────────┤
│  $[XX,XXX]         │  Origen: [desglose específico]             │
│  COSTO MENSUAL     │                                            │
│  DE NO ACTUAR      │                                            │
│  $[XXX,XXX] / año  │                                            │
├─────────────────────────────────────────────────────────────────┤
│  05. EL CAMINO DE TRANSFORMACIÓN                                │
│  FASE 1 DOLOR     │ [Nombre] — [Qué resuelve | semanas]         │
│  FASE 2 EVIDENCIA │ [Nombre] — [Qué construye]                  │
│  FASE 3 AUTONOMÍA │ [Nombre] — [Qué deja instalado]             │
│  Horizonte: [N] meses.                                          │
├─────────────────────────────────────────────────────────────────┤
│  06. LA RUTA PROPUESTA                                          │
│  LO QUE INNOVERSE CONSTRUYE CONTIGO                             │
│  | Qué construimos | Producto | Horizonte |                     │
│  LO QUE TU ORGANIZACIÓN DEBE RESOLVER                           │
│  | Qué debes resolver | Por qué | Riesgo si no |                │
│  [Condición de arranque si existe Cat. C]                       │
├─────────────────────────────────────────────────────────────────┤
│  The door to success. — InnoVerse Solutions    Confidencial      │
└─────────────────────────────────────────────────────────────────┘
```

**Checklist A10 (8 criterios — todos deben cumplirse):**
- [ ] Situación Actual no puede copiarse a ningún otro cliente
- [ ] Causas raíz pasan el test contrafáctico (causalidad verificable)
- [ ] Bloque 4 tiene IDD + Cost of Delay mensual + anual + origen del número
- [ ] Sin nombres de frameworks, abreviaturas técnicas sin traducción, ni frases de marketing
- [ ] Director sin conocimiento de metodología lo lee en 3 min y dice "así somos"
- [ ] Bloque 6 distingue con precisión qué ejecuta InnoVerse y qué debe resolver el cliente
- [ ] Solo aparecen productos reales del portafolio InnoVerse actual en la tabla A
- [ ] Condición de arranque presente si existe iniciativa Cat. C

### 10.2 Reporte Completo (A11)

El Reporte Completo es el documento de referencia para el equipo directivo y operativo del cliente. Se presenta en la semana posterior a la reunión de cierre. 8–12 páginas con trazabilidad completa de evidencia.

**Diferencias clave vs. One-Pager:**

| Aspecto | One-Pager (A8) | Reporte Completo (A11) |
|---------|----------------|------------------------|
| Input | Solo A7 síntesis | A7 síntesis + A1–A6 dimensionales |
| Extensión | 1 página | 8–12 páginas |
| Audiencia | Dirección (3 min) | Dirección + operaciones (60–90 min) |
| Hallazgos | Destilados | Con evidencia de origen |
| Causalidad | Enunciada | Con test contrafáctico explícito |
| Quality gate | A10 (8 criterios) | Sin quality gate |
| Paralelo con | A11 | A8 |

---

## 11. Protocolo de Sesión de Síntesis Interna

La sesión de síntesis interna ocurre después de que los agentes A1–A6 completan sus análisis y son aprobados por A9.

### Protocolo de 4 pasos

**Paso 1 — Presentaciones dimensionales (5 min por dimensión máx.)**
Cada agente presenta sus 3 hallazgos principales. No enumera debilidades: presenta evidencia de patrón — qué se observó, en cuántas instancias, qué consecuencia genera, qué tan generalizado es.

**Paso 2 — Patrones transversales**
El equipo identifica cómo un hallazgo aislado en Tecnología conecta con un problema de Cultura o Procesos. Busca interdependencias, no scores independientes.

**Paso 3 — Árbol de causalidad (diálogo socrático)**
Desafía interpretaciones superficiales. Para cada candidata a causa raíz, pregunta: "¿Si esto mejora, mejora el síntoma sin tocar nada más?" Si la respuesta es no, excava más profundo.

**Paso 4 — Narrativa diagnóstica borrador**
Redacta una narrativa de máximo 1 página. Sin gráficos ni tablas. La prueba de calidad: "¿El director ejecutivo del cliente puede leer esto y decir: *Así es exactamente. Han visto lo que nadie más vio.*?"

### Regla de oro

> **Máximo 3 causas raíz por cliente.** Si el equipo identifica más de 3, significa que no ha profundizado suficientemente en la lógica causal.

---

## 12. Reglas de Negocio Invariables

Estas reglas no pueden ser ignoradas por ningún agente bajo ninguna circunstancia:

1. **Nunca mencionar frameworks al cliente.** Usar siempre lenguaje de resultados de negocio.

2. **Máximo 3 causas raíz.** Si hay más, el análisis no es suficientemente profundo.

3. **La causa raíz casi nunca está en Tecnología.** Invariablemente está en Estrategia, Liderazgo o Cultura.

4. **No asignar nivel de madurez por cuestionario único.** Requiere evidencia confirmatoria de múltiples fuentes.

5. **Aplicar factores de conservadurismo al ROI.** Reducción de costo × 70%. Aumento de revenue × 50%.

6. **La Resistencia Silenciosa no se detecta con cuestionarios.** Solo con observación etnográfica de flujo de trabajo.

7. **Los entregables deben ser completamente únicos para cada cliente.** Ninguna sección puede copiarse entre diagnósticos.

8. **CB es obligatorio antes de lanzar A1–A6.** El contrato personaliza el diagnóstico. Sin contrato no hay pipeline.

9. **A9 es obligatorio después de cada agente dimensional.** No se salta el quality gate. FAIL tras 2 retries = escala a humano.

10. **A10 es obligatorio antes de entregar el One-Pager.** El One-Pager no se entrega al cliente sin aprobación de A10.

11. **A11 corre en paralelo con A8.** Ambos reciben la síntesis de A7. A11 también usa los outputs A1–A6.

12. **El diagnóstico determina el punto de entrada a la metodología InnoVerse:**
    - Procesos informales + datos débiles → Data Engineering primero
    - Arquitectura sólida pero sin inteligencia → Business Intelligence primero
    - Ambas cosas maduras → ML & AI directo

13. **Nunca sobreprometer ROI.** Es mejor sorprender al alza que desilusionar.

14. **Toda estimación financiera incluye su desglose de origen** (qué proceso, qué área, qué margen).

15. **El Bloque 6 y la Sección 9 del Reporte solo incluyen productos del portafolio InnoVerse actual:** DataReady Assessment, System Technical Advisory, First Intelligence Project, Intelligent Data Platform.

---

## 13. Glosario de Frameworks

Referencia interna para consultores. Nunca compartir con clientes.

| Framework | Autor(es) | Año | Dimensión InnoVerse | Descripción |
|-----------|-----------|-----|---------------------|-------------|
| ADKAR | Hiatt, J. | 2003 | Cultura & Liderazgo | Gestión del cambio individual: Awareness, Desire, Knowledge, Ability, Reinforcement. |
| Analytics Maturity | Gartner | 2020–2025 | Datos | Descriptiva → Diagnóstica → Predictiva → Prescriptiva. |
| Bimodal IT | Gartner | 2014–2025 | Tecnología | Mode 1 (estable) y Mode 2 (experimental) operando en paralelo. |
| BPM/BPMM | OMG & CMMI | 2008–2025 | Procesos | Madurez de gestión de procesos: Inicial → Gestionado → Optimizado. |
| Business Model Canvas | Osterwalder & Pigneur | 2010 | Estrategia | 9 bloques para modelar propuesta de valor. |
| DAMA-DMBOK 3.0 | DAMA International | 2025 | Datos | 11 dominios de gestión de datos. Incluye gobernanza de IA. |
| DECA+ | InnoVerse | 2024–2025 | Transformación | Marco propio: Dolor → Evidencia → Capacidad → Autonomía. Backlog en categorías A/B/C. |
| Designed for Digital | MIT CISR | 2019 | Transformación | 5 componentes: Customer Knowledge, Operational Backbone, Digital Platform, Accountability, External Developers. |
| Dynamic Capabilities | Teece, D. | 2007–2025 | Estrategia | Cómo empresas crean ventaja competitiva mediante capacidades dinámicas. |
| Gartner Hype Cycle | Gartner | 1995–2025 | Tecnología | Curva de adopción: Innovation Trigger → Peak Hype → Trough → Slope → Plateau. |
| Heifetz Adaptive Leadership | Heifetz, R. | 1994–2025 | Liderazgo | Distinción técnico vs. adaptativo. Navegar cambio complejo. |
| Hyperautomation | Gartner | 2018–2025 | Procesos & Tecnología | RPA → RPA Cognitiva → Hiperautomatización. |
| Kotter 8-Step | Kotter, J. | 1996–2025 | Liderazgo & Cultura | 8 pasos para liderar cambio: urgencia, coalición, visión, comunicación, empoderamiento, quick wins, consolidación, institucionalización. |
| Lean Six Sigma | George, M. | 2002–2025 | Procesos | Lean (flujo) + Six Sigma (calidad): eliminar desperdicios y variación. |
| McKinsey 3 Horizons | Baghai, M. | 2000–2025 | Estrategia | H1 (core actual), H2 (negocios emergentes), H3 (opciones futuras). |
| Operational Backbone | Ross & Weill, MIT CISR | 2002–2025 | Procesos & Tecnología | Arquitectura operacional integrada para eficiencia, control y agilidad simultáneos. |
| SMACIT | MIT CISR | 2012–2025 | Tecnología | Social, Mobile, Analytics, Cloud, Internet of Things. |
| Value Stream Mapping | Rother & Shook | 1998–2025 | Procesos | Técnica Lean para mapear flujo de valor desde materia prima hasta cliente. |

---

## Notas de versión

**v2.0 (Mayo 2026) — Harness v3**
- Migración completa a **Claude Managed Agents**: 12 Agent objects persistentes (A1–A11 + CB). `SessionRunner` reemplaza `AsyncLLMClient` en todo el pipeline.
- **CB — Contract Builder**: nuevo agente pre-pipeline que genera el contrato de diagnóstico personalizado por cliente.
- **A9 — Quality Gate**: nuevo agente evaluador ejecutado después de cada A1–A6. Retry hasta 2× con escalado a humano.
- **A10 — Onepager Evaluator**: nuevo agente evaluador del One-Pager contra checklist de 8 criterios.
- **A11 — Reporte Completo**: nuevo agente que genera 8–12 páginas en paralelo con A8. Usa A7 + A1–A6 como input.
- **A8 actualizado**: Bloque 6 (La Ruta Propuesta) agregado con dos tablas DECA+ y condición de arranque. 6 filtros de test de reconocimiento (vs. 5 en v1.0).
- **Sección 10**: actualizada para incluir ambos entregables (One-Pager + Reporte Completo), checklist A10, y tabla comparativa.
- **Sección 12**: 15 reglas de negocio (vs. 10 en v1.0). Reglas 8–11 y 15 son nuevas.
- **Infraestructura**: FastAPI REST (`api/`), JWT auth (`auth/`), OpenTelemetry (`telemetry/`), Teams Bot (`teams_bot/`).
- `config/antipatrones.json` (v1.0) movido a `legacy/`. Canónico: `config/antipatterns.json` (v2.0).

**v1.0 (2026)**
Primera versión del sistema agéntico DiagnostiCore. 8 sub-agentes (A1–A8), 7 herramientas compartidas, escala 1–5 para 6 dimensiones, 7 anti-patrones documentados, protocolo completo de síntesis interna.

---

*InnoVerse Solutions | DiagnostiCore — Sistema Agéntico de Diagnóstico 360*
*Uso exclusivo del equipo InnoVerse. Confidencial.*
