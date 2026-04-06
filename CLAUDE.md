# DiagnostiCore — Instrucciones de Proyecto para Claude Code

## Identidad del sistema

**DiagnostiCore** es el sistema agéntico de InnoVerse que automatiza el Diagnóstico 360 de transformación digital. Diagnostica organizaciones en seis dimensiones y entrega un One-Pager accionable al cliente.

Lee `SKILL.md` como la referencia principal de la arquitectura, metodología, escalas de madurez y reglas de negocio invariables.

---

## Estructura de directorios

| Directorio / Archivo | Propósito |
|----------------------|-----------|
| `agents/` | Prompts de cada sub-agente (A1–A10). **Lee el archivo completo antes de modificar cualquier agente.** |
| `blackboard/` | Módulo Python de estado compartido + persistencia entre sesiones |
| `blackboard/diagnostico-state.json` | Fuente única de verdad del diagnóstico activo (estado de pipeline, quality-gate, contratos) |
| `blackboard/contracts/` | Contratos pre-diagnóstico generados por `contract_builder.py` |
| `blackboard/outputs/` | Outputs JSON dimensionales de A1–A6 |
| `blackboard/evaluations/` | Evaluaciones de A9 quality-gate por dimensión |
| `blackboard/synthesis/` | Output de A7 síntesis |
| `blackboard/onepager/` | Output de A8 + evaluación de A10 |
| `config/` | Configuración del sistema (pesos IDD, escalas, anti-patrones, criterios) |
| `orchestrator/` | Lógica de orquestación del pipeline A1→A8 + evaluadores |
| `runs/` | Blackboards completos por run (formato `CLIENTE_YYYYMMDD.json`). **Nunca elimines archivos aquí.** |
| `legacy/` | Versiones anteriores de prompts. **Nunca elimines archivos aquí.** |
| `tools/` | Scripts de cálculo compartidos (IDD, costo de inacción, detección de anti-patrones) |
| `examples/` | Ejemplos de diagnósticos completos |

---

## Pipeline v2 (harness design)

```
[Evidencia del cliente]
        │
        ▼
[contract_builder] → contrato específico del cliente
        │
        ▼
[A1–A6] análisis dimensional (con contrato como input adicional)
        │
        ▼
[A9 quality-gate] evalúa CADA output dimensional
    PASS → continúa │ FAIL → feedback → retry (máx 2x) → escala a humano
        │
        ▼
[A7 síntesis] con outputs evaluados y aprobados
        │
        ▼
[A8 output] genera One-Pager
        │
        ▼
[A10 onepager-eval] valida checklist de 8 criterios
    PASS → entregable │ FAIL → feedback → retry (máx 2x)
        │
        ▼
[ENTREGABLE APROBADO]
```

---

## Estado del diagnóstico activo

Al iniciar cada sesión, el primer comando debe ser:

```
Lee blackboard/diagnostico-state.json y dime en qué fase del pipeline
estamos y cuál es la próxima tarea pendiente.
```

Si no existe el archivo de estado, significa que es un diagnóstico nuevo.

---

## Reglas de operación

1. **Todos los outputs de agentes van en formato JSON.** Sin excepciones.
2. **Antes de modificar cualquier agente**, lee su archivo `.md` completo en `agents/`.
3. **El quality-gate (A9) debe ejecutarse después de cada A1–A6.** No saltar este paso.
4. **El contrato del cliente se genera ANTES de lanzar los agentes dimensionales.**
5. **El One-Pager debe ser aprobado por A10** antes de considerarse entregable.
6. **Nunca elimines archivos en `runs/` ni en `legacy/`.**
7. **La causa raíz casi nunca está en Tecnología** — ver SKILL.md Sección 12.
8. **Nunca menciones frameworks al cliente** — lenguaje de resultados de negocio siempre.

---

## Archivos de configuración clave

| Archivo | Contenido |
|---------|-----------|
| `config/maturity_scales.json` | Escalas 1–5 por dimensión con evidencias clave |
| `config/antipatterns.json` | 7 anti-patrones con dimensiones donde buscarlos |
| `config/acceptance_criteria.json` | Checklist de 8 criterios para el One-Pager |
| `config/pesos_idd.json` | Pesos del Índice de Deuda Digital por dimensión |

---

## Convenciones de código

- Python 3.11+, async/await para llamadas LLM
- File locking con `fcntl`/`msvcrt` para escrituras concurrentes en el state
- Todos los IDs de diagnóstico siguen el formato: `DX-{AAAA}-{NNN}` o `CLIENTE_YYYYMMDD`
- Los logs usan `logging.getLogger(__name__)` — nunca `print()` en producción
