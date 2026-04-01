"""
DiagnostiCore — Calculadora del Índice de Deuda Digital (IDD)
==============================================================
Convierte los scores de madurez de las 6 dimensiones en el IDD global
en escala 0-100, donde 0 = máxima deuda digital y 100 = sin deuda.

Uso:
    from tools.calcular_idd import calcular_idd, interpretar_idd

    scores = {
        "estrategia": 2,
        "liderazgo": 2,
        "cultura": 1,
        "procesos": 2,
        "datos": 1,
        "tecnologia": 3
    }
    resultado = calcular_idd(scores)
    print(resultado)
"""

from typing import Dict, Tuple


# Pesos ponderados por dimensión (suma = 100%)
PESOS_IDD = {
    "estrategia":  0.25,   # 25% — Su ausencia bloquea todas las demás
    "liderazgo":   0.18,   # 18% — Convierte estrategia en comportamiento organizacional
    "cultura":     0.20,   # 20% — Resiste o habilita todas las dimensiones
    "procesos":    0.15,   # 15% — Backbone operacional de la transformación
    "datos":       0.12,   # 12% — Habilitador de decisiones informadas
    "tecnologia":  0.10,   # 10% — Habilitadora, no primaria
}

DIMENSIONES_REQUERIDAS = list(PESOS_IDD.keys())

# Benchmarks de percentil para sector PYME México
RANGOS_IDD = [
    (0,  25,  "Percentil 5–20",  "Deuda digital crítica. Riesgo operacional inminente."),
    (26, 45,  "Percentil 20–40", "Deuda alta. Margen significativo de mejora. Oportunidad comercial clara."),
    (46, 60,  "Percentil 40–60", "Deuda moderada. Brechas específicas identificables. Transformación enfocada."),
    (61, 75,  "Percentil 60–80", "Deuda baja. Optimización y aceleración. Ventaja competitiva alcanzable."),
    (76, 100, "Percentil 80–95", "Capacidad digital sólida. Innovación como próximo paso."),
]


def calcular_idd(scores: Dict[str, int]) -> Dict:
    """
    Calcula el Índice de Deuda Digital a partir de los scores de madurez.

    Args:
        scores: Diccionario con scores 1-5 para cada dimensión.
                Todas las dimensiones son requeridas.

    Returns:
        Diccionario con IDD, desglose por dimensión, interpretación y recomendaciones.

    Raises:
        ValueError: Si falta alguna dimensión o los scores están fuera de rango.
    """
    # Validaciones
    _validar_scores(scores)

    # Cálculo
    deuda_ponderada = 0.0
    desglose = {}

    for dim, peso in PESOS_IDD.items():
        score = scores[dim]
        # Convierte madurez a % de deuda: score 5 = 0% deuda, score 1 = 100% deuda
        pct_deuda = (5 - score) / 4 * 100
        contribucion = pct_deuda * peso

        desglose[dim] = {
            "score_madurez": score,
            "pct_deuda_dimension": round(pct_deuda, 1),
            "peso": f"{int(peso * 100)}%",
            "contribucion_idd": round(contribucion, 2),
            "nivel_nombre": _nombre_nivel(score)
        }
        deuda_ponderada += contribucion

    idd = round(100 - deuda_ponderada, 1)
    idd = max(0, min(100, idd))  # Clamp 0-100

    # Interpretación
    percentil, interpretacion = _interpretar(idd)

    # Dimensión más débil (mayor contribución a la deuda)
    dim_mas_debil = max(desglose, key=lambda d: desglose[d]["contribucion_idd"])
    dim_mas_fuerte = min(desglose, key=lambda d: desglose[d]["contribucion_idd"])

    return {
        "idd": idd,
        "clasificacion": percentil,
        "interpretacion": interpretacion,
        "desglose": desglose,
        "dimension_mas_debil": {
            "nombre": dim_mas_debil,
            "score": scores[dim_mas_debil],
            "contribucion_deuda_pct": round(desglose[dim_mas_debil]["contribucion_idd"], 1)
        },
        "dimension_mas_fuerte": {
            "nombre": dim_mas_fuerte,
            "score": scores[dim_mas_fuerte]
        },
        "barras_visuales": _generar_barras(scores),
        "resumen_texto": _generar_resumen(idd, scores, dim_mas_debil, percentil)
    }


def interpretar_idd(idd: float) -> Tuple[str, str]:
    """Retorna (percentil, interpretación) para un IDD dado."""
    return _interpretar(idd)


def _validar_scores(scores: Dict[str, int]) -> None:
    faltantes = [d for d in DIMENSIONES_REQUERIDAS if d not in scores]
    if faltantes:
        raise ValueError(
            f"Dimensiones faltantes en scores: {faltantes}\n"
            f"Requeridas: {DIMENSIONES_REQUERIDAS}"
        )

    for dim, score in scores.items():
        if dim not in DIMENSIONES_REQUERIDAS:
            raise ValueError(f"Dimensión no reconocida: '{dim}'. Válidas: {DIMENSIONES_REQUERIDAS}")
        if not isinstance(score, int) or not (1 <= score <= 5):
            raise ValueError(
                f"Score inválido para '{dim}': {score}. "
                f"Debe ser entero entre 1 y 5."
            )


def _nombre_nivel(score: int) -> str:
    nombres = {1: "Reactivo", 2: "Consciente", 3: "Inflexión", 4: "Integrado", 5: "Transformacional"}
    return nombres.get(score, "Desconocido")


def _interpretar(idd: float) -> Tuple[str, str]:
    for min_val, max_val, percentil, descripcion in RANGOS_IDD:
        if min_val <= idd <= max_val:
            return percentil, descripcion
    return "Fuera de rango", "IDD fuera del rango esperado."


def _generar_barras(scores: Dict[str, int]) -> str:
    """Genera representación visual de las barras de madurez para el One-Pager."""
    etiquetas = {
        "estrategia": "Estrategia",
        "liderazgo":  "Liderazgo ",
        "cultura":    "Cultura   ",
        "procesos":   "Procesos  ",
        "datos":      "Datos     ",
        "tecnologia": "Tecnología"
    }
    lineas = []
    for dim in DIMENSIONES_REQUERIDAS:
        score = scores.get(dim, 0)
        filled = "■" * score
        empty = "□" * (5 - score)
        etiqueta = etiquetas.get(dim, dim)
        lineas.append(f"{etiqueta} {filled}{empty} {score}/5")
    return "\n".join(lineas)


def _generar_resumen(idd: float, scores: Dict, dim_debil: str, percentil: str) -> str:
    """Genera texto de resumen ejecutivo del IDD."""
    nombre_debil = {
        "estrategia": "Estrategia",
        "liderazgo": "Liderazgo",
        "cultura": "Cultura",
        "procesos": "Procesos",
        "datos": "Datos",
        "tecnologia": "Tecnología"
    }.get(dim_debil, dim_debil)

    score_debil = scores[dim_debil]

    return (
        f"IDD: {idd}/100 ({percentil}). "
        f"La dimensión con mayor deuda es {nombre_debil} (nivel {score_debil}/5), "
        f"que representa la mayor palanca de mejora del sistema."
    )


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    # Ejemplo de uso rápido
    scores_ejemplo = {
        "estrategia": 2,
        "liderazgo": 2,
        "cultura": 1,
        "procesos": 2,
        "datos": 1,
        "tecnologia": 3
    }

    if len(sys.argv) > 1:
        # Acepta JSON desde CLI: python calcular_idd.py '{"estrategia":2,...}'
        scores_ejemplo = json.loads(sys.argv[1])

    resultado = calcular_idd(scores_ejemplo)

    print(f"\n{'='*50}")
    print(f"ÍNDICE DE DEUDA DIGITAL: {resultado['idd']}/100")
    print(f"Clasificación: {resultado['clasificacion']}")
    print(f"Interpretación: {resultado['interpretacion']}")
    print(f"\nPERFIL DE MADUREZ:")
    print(resultado['barras_visuales'])
    print(f"\nDimensión más débil: {resultado['dimension_mas_debil']['nombre']} "
          f"(Score {resultado['dimension_mas_debil']['score']}/5)")
    print(f"\nDESGLOSE:")
    for dim, info in resultado['desglose'].items():
        print(f"  {dim:12} | {info['score_madurez']}/5 | {info['nivel_nombre']:15} | "
              f"Deuda: {info['pct_deuda_dimension']:5.1f}% | Contribución: {info['contribucion_idd']:5.2f}pts")
    print(f"{'='*50}\n")
