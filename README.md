# DiagnostiCore — Sistema Agéntico de Diagnóstico 360
## InnoVerse Solutions | Versión 1.0 | Confidencial

> *"El 70–80% de los fracasos en transformación digital tiene causas organizacionales, no técnicas."*
> — MIT CISR (Ross, Weill, Sebastian, 2019)

---

## ¿Qué es esto?

**DiagnostiCore** es el sistema agéntico de InnoVerse que convierte la evidencia cruda de un levantamiento de diagnóstico en una narrativa ejecutiva accionable. Automatiza los análisis de seis dimensiones de madurez digital, los integra en un árbol de causalidad, calcula el Índice de Deuda Digital (IDD) y genera el One-Pager que se entrega al cliente.

---

## Estructura del skill

```
DiagnostiCore — Arquitectura/
│
├── SKILL.md                    ← Especificación completa del sistema (leer primero)
├── README.md                   ← Este archivo
│
├── agents/                     ← System prompts de cada sub-agente
│   ├── A1_estrategia.md        Dimensión 1: Estrategia y Modelos de Negocio
│   ├── A2_liderazgo.md         Dimensión 2: Liderazgo y Organizaciones
│   ├── A3_cultura.md           Dimensión 3: Cultura y Gestión del Cambio
│   ├── A4_procesos.md          Dimensión 4: Procesos y Operaciones
│   ├── A5_datos.md             Dimensión 5: Datos, Analítica e BI
│   ├── A6_tecnologia.md        Dimensión 6: Tecnología y Arquitectura Digital
│   ├── A7_sintesis.md          Motor de Síntesis — causas raíz e IDD
│   └── A8_one_pager.md         Generador del entregable final
│
├── blackboard/                 ← Estado compartido entre agentes
│   ├── schema.json             Esquema JSON de validación
│   ├── template.json           Template vacío para nuevo run
│   └── blackboard.py          Manager Python (leer/escribir estado)
│
├── tools/                      ← Scripts de cómputo compartidos
│   ├── calcular_idd.py         Calcula IDD ponderado (0-100)
│   ├── detectar_antipatron.py  Detecta 7 anti-patrones por análisis textual
│   └── cuantificar_costo.py    Calcula Cost of Delay con factores conservadores
│
├── config/                     ← Configuración del sistema
│   ├── pesos_idd.json          Pesos por dimensión + interpretación de rangos
│   ├── antipatrones.json       Catálogo completo de 7 anti-patrones
│   └── brand_guidelines.json   Identidad visual y reglas de lenguaje InnoVerse
│
├── examples/                   ← Ejemplos de referencia
│   └── CompoLat_ejemplo.json   Caso manufacturero del Book 360
│
└── runs/                       ← Diagnósticos activos (confidencial por cliente)
    └── CLIENTE_YYYYMMDD.json   Un archivo por diagnóstico
```

---

## Cómo iniciar un nuevo diagnóstico

### Opción A — Desde Python

```python
from blackboard.blackboard import Blackboard

# 1. Crear el run
bb = Blackboard.crear_run(
    nombre_cliente="NombreEmpresa",
    sector="manufactura",          # o: inmobiliario, comercializadora, servicios
    consultor="Tu Nombre",
    tamaño="mediana",
    empleados=200,
    runs_dir="runs"
)

# 2. Agregar evidencia
bb.add_evidencia_transcripcion(
    entrevistado_rol="Director General",
    texto="[Transcripción de la entrevista DECA...]",
    dimension_primaria="estrategia"
)

# 3. Ver estado
print(bb.to_markdown_resumen())
```

### Opción B — Desde CLI

```bash
# Crear nuevo run
python blackboard/blackboard.py nuevo "NombreEmpresa" "manufactura" "Consultor" "runs/"

# Ver estado de un run
python blackboard/blackboard.py status runs/NOMBREEMPRESA_20260330.json
```

### Opción C — Manual

1. Copia `blackboard/template.json` a `runs/CLIENTE_YYYYMMDD.json`
2. Llena los campos del cliente
3. Agrega la evidencia en las secciones correspondientes

---

## Flujo de un diagnóstico completo

```
LEVANTAMIENTO
  Entrevistas DECA + Cuestionarios + Auditoría técnica + Mapas de proceso + Series financieras
  ↓
ANÁLISIS DIMENSIONAL (A1–A6 en paralelo)
  Cada agente lee la evidencia de su dimensión del blackboard
  Asigna nivel 1–5 con justificación multifuente
  Detecta anti-patrones
  Escribe resultado en blackboard
  ↓
SÍNTESIS (A7)
  Lee todos los resultados dimensionales del blackboard
  Identifica patrones transversales
  Aplica árbol de causalidad → máximo 3 causas raíz
  Calcula IDD ponderado
  Cuantifica Cost of Delay
  Diseña camino DECA+ en 3 fases
  ↓
OUTPUT (A8)
  Lee la síntesis del blackboard
  Genera One-Pager en lenguaje ejecutivo (sin jerga técnica)
  Aplica verificación anti-jerga y factores de conservadurismo
  Produce documento listo para entrega al cliente
```

---

## Calcular el IDD manualmente

```bash
python tools/calcular_idd.py '{"estrategia":2,"liderazgo":2,"cultura":1,"procesos":2,"datos":1,"tecnologia":3}'
```

## Detectar anti-patrones en texto

```bash
python tools/detectar_antipatron.py analizar "El director aprueba todo. Cada área tiene su propio Excel."

# Ver catálogo completo
python tools/detectar_antipatron.py listar
```

## Calcular costo de inacción

```bash
python tools/cuantificar_costo.py
# Ejecuta el demo con caso CompoLat
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
| **One-Pager único por cliente** | Ninguna sección puede copiarse entre diagnósticos |
| **Resistencia silenciosa** | No se detecta con cuestionarios, solo con observación etnográfica |

---

## Recursos de referencia

| Recurso | Ubicación |
|---------|-----------|
| Fundamento teórico completo | `InnoVerse_Book_Diagnostico_360_v1.docx` |
| Template Word del One-Pager | `ONE_PAGER_InnoVerse_template_v1.docx` |
| Especificación del sistema agéntico | `SKILL.md` |
| Ejemplo de diagnóstico bien construido | `examples/CompoLat_ejemplo.json` |

---

*InnoVerse Solutions | DiagnostiCore v1.0 | Uso exclusivo del equipo InnoVerse. Confidencial.*
