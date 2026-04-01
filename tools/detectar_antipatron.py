"""
DiagnostiCore — Detector de Anti-Patrones
==========================================
Analiza evidencia textual y detecta los 7 anti-patrones documentados
por InnoVerse en más del 70% de sus diagnósticos.

Uso:
    from tools.detectar_antipatron import detectar_antipatrones

    evidencia = "El director aprueba todas las órdenes de compra.
                 Cada departamento tiene su propio Excel con inventario."

    resultado = detectar_antipatrones(evidencia)
    for ap in resultado:
        print(ap["nombre"], "-", ap["riesgo"])
"""

import re
from typing import List, Dict, Any


# Catálogo completo de anti-patrones con señales de detección
CATALOGO_ANTIPATRONES = [
    {
        "id": "excel_sagrado",
        "nombre": "El Excel Sagrado",
        "descripcion": (
            "Información crítica del negocio reside en spreadsheets personales "
            "en laptops individuales o servidores ad-hoc sin backup sistemático."
        ),
        "prevalencia": ">80% de diagnósticos InnoVerse",
        "raiz_causal": "gobernanza_datos_cultura",
        "no_es": "un problema de tecnología",
        "riesgo_principal": (
            "Punto único de falla: si el empleado se va, la información se va con él. "
            "Hace imposible automatización o integración."
        ),
        "señales_textuales": [
            r"excel\b", r"hoja\s+de\s+c[aá]lculo", r"spreadsheet",
            r"archivo\s+personal", r"mi\s+excel", r"excel\s+propio",
            r"datos\s+en\s+excel", r"reportes\s+en\s+excel",
            r"cada\s+uno\s+tiene\s+su\s+(propio\s+)?excel",
            r"shadow\s+it", r"archivo\s+personal"
        ],
        "señales_conceptuales": [
            "datos en archivos individuales",
            "información en computadoras personales",
            "reportes manuales en hojas",
            "cada departamento su propio archivo"
        ],
        "dimension_primaria": "datos",
        "dimensiones_secundarias": ["procesos", "cultura"],
        "impacto_idd": "alto"
    },
    {
        "id": "director_orquesta",
        "nombre": "El Director Orquesta",
        "descripcion": (
            "El director general toma todas las decisiones y es el cuello de botella "
            "operativo. El equipo espera instrucción para cualquier decisión fuera del flujo diario."
        ),
        "prevalencia": ">70% de diagnósticos InnoVerse",
        "raiz_causal": "liderazgo_cultura",
        "no_es": "un fracaso de carácter, sino una brecha de competencia",
        "riesgo_principal": (
            "Fragilidad organizacional extrema. Cualquier ausencia del director paraliza operaciones. "
            "La empresa escala hasta el tamaño que puede manejar una sola persona."
        ),
        "señales_textuales": [
            r"el\s+(dueño|director|CEO|gerente)\s+(aprueba|decide|autoriza|revisa)\s+todo",
            r"sin\s+(el\s+)?(dueño|director)\s+no\s+(se\s+puede|podemos)",
            r"hay\s+que\s+preguntarle\s+al\s+director",
            r"todo\s+pasa\s+por\s+[él|ella]",
            r"nadie\s+decide\s+sin\s+[él|ella]",
            r"centraliz", r"cuello\s+de\s+botella",
            r"depende\s+(de\s+)?(él|ella|del\s+director|del\s+dueño)"
        ],
        "señales_conceptuales": [
            "director aprueba todo",
            "sin el director no se puede",
            "todo centralizado en una persona",
            "equipo espera instrucciones"
        ],
        "dimension_primaria": "liderazgo",
        "dimensiones_secundarias": ["procesos", "cultura"],
        "impacto_idd": "crítico"
    },
    {
        "id": "isla_automatizacion",
        "nombre": "La Isla de Automatización",
        "descripcion": (
            "Un departamento logró automatización exitosa mientras el resto permanece manual. "
            "Genera ilusión de progreso y brechas de integración."
        ),
        "prevalencia": ">60% de diagnósticos InnoVerse",
        "raiz_causal": "estrategia_procesos",
        "no_es": "evidencia de transformación exitosa",
        "riesgo_principal": (
            "El director ve un departamento automatizado y cree que la empresa es moderna. "
            "En realidad existe desconexión fundamental entre sistemas."
        ),
        "señales_textuales": [
            r"(contabilidad|finanzas|producción|almacén)\s+(ya\s+)?(tiene|usa|implementó)\s+(sistema|software|ERP)",
            r"solo\s+(un|el)\s+departamento",
            r"(el\s+resto|los\s+demás)\s+(sigue|está)\s+manual",
            r"no\s+(están|estamos)\s+conectados",
            r"islas\s+(de\s+)?información",
            r"cada\s+área\s+su\s+propio\s+sistema"
        ],
        "señales_conceptuales": [
            "solo un área tiene sistema",
            "el resto trabaja manual",
            "no están integrados",
            "cada departamento su propio sistema"
        ],
        "dimension_primaria": "procesos",
        "dimensiones_secundarias": ["estrategia", "tecnologia"],
        "impacto_idd": "medio"
    },
    {
        "id": "resistencia_silenciosa",
        "nombre": "Resistencia Silenciosa",
        "descripcion": (
            "La gerencia media dice sí en las reuniones pero sabotea la adopción por inacción. "
            "Es el anti-patrón más peligroso porque es invisible en evaluaciones formales."
        ),
        "prevalencia": ">65% de diagnósticos InnoVerse",
        "raiz_causal": "cultura_liderazgo",
        "no_es": "detectable por cuestionarios, requiere observación etnográfica",
        "riesgo_principal": (
            "Las iniciativas que requieren participación de gerencia media se evaporan "
            "entre el anuncio y la ejecución."
        ),
        "señales_textuales": [
            r"en\s+reuniones\s+dicen\s+s[íi]",
            r"en\s+pasillos\s+dicen\s+(que\s+)?(no|no\s+va\s+a\s+funcionar)",
            r"nadie\s+lo\s+usa",
            r"implementamos\s+pero\s+no\s+(lo\s+)?(usan|adoptaron)",
            r"compramos\s+el\s+sistema\s+pero",
            r"capacitamos\s+pero\s+(nadie|no)\s+(aplica|usa)",
            r"resistencia", r"rechazo", r"no\s+quieren\s+cambiar",
            r"siguen\s+haciendo\s+lo\s+mismo"
        ],
        "señales_conceptuales": [
            "dicen sí pero no hacen",
            "nadie usa el sistema nuevo",
            "capacitamos pero no adoptaron",
            "implementamos pero no funciona"
        ],
        "dimension_primaria": "cultura",
        "dimensiones_secundarias": ["liderazgo", "procesos"],
        "impacto_idd": "crítico"
    },
    {
        "id": "erp_fantasma",
        "nombre": "El ERP Fantasma",
        "descripcion": (
            "Sistema empresarial adquirido e implementado, pero solo se utilizan "
            "el 20-30% de sus funcionalidades. Las capacidades analíticas están dormidas."
        ),
        "prevalencia": ">50% de diagnósticos con ERP",
        "raiz_causal": "estrategia_cultura_liderazgo",
        "no_es": "un problema técnico del ERP",
        "riesgo_principal": (
            "Costo hundido masivo + cinismo organizacional: 'Para qué invertir en tecnología si no la usamos.'"
        ),
        "señales_textuales": [
            r"ERP\b", r"SAP\b", r"oracle\b", r"microsoft\s+dynamics", r"odoo",
            r"solo\s+(usamos|utilizamos)\s+(el\s+)?(\d+)%",
            r"compramos\s+(el\s+)?sistema\s+(hace\s+)?\d+\s+años",
            r"no\s+(lo\s+)?(usamos|aprovechamos)\s+(bien|al\s+máximo|todo)",
            r"funcionalidades\s+(sin\s+usar|dormidas|sin\s+activar)",
            r"pagamos\s+licencias\s+que\s+no\s+usamos",
            r"módulos\s+sin\s+implementar"
        ],
        "señales_conceptuales": [
            "ERP que no se usa completamente",
            "solo usan una parte del sistema",
            "compraron sistema hace años",
            "muchas funciones sin usar"
        ],
        "dimension_primaria": "tecnologia",
        "dimensiones_secundarias": ["cultura", "procesos", "estrategia"],
        "impacto_idd": "alto"
    },
    {
        "id": "datos_no_hablan",
        "nombre": "Datos que No Hablan",
        "descripcion": (
            "La organización recopila datos y genera reportes regularmente, "
            "pero los reportes no se leen y las decisiones se toman por intuición."
        ),
        "prevalencia": ">55% de diagnósticos InnoVerse",
        "raiz_causal": "cultura (ausencia de preguntas, no de datos)",
        "no_es": "un problema técnico de datos",
        "riesgo_principal": (
            "Los datos existen pero no hay cultura de inteligencia. "
            "Los reportes se producen por compliance, no por valor."
        ),
        "señales_textuales": [
            r"tenemos\s+(datos|reportes)\s+pero\s+nadie\s+los\s+(usa|lee|revisa)",
            r"reportes\s+que\s+nadie\s+lee",
            r"se\s+generan\s+reportes\s+pero",
            r"datos\s+existen\s+pero\s+no\s+(se\s+usan|sirven)",
            r"no\s+(confiamos|confían)\s+en\s+(los\s+)?datos",
            r"decidimos\s+por\s+intuición",
            r"nadie\s+confía\s+en\s+(los\s+)?números",
            r"datos\s+inconsistentes"
        ],
        "señales_conceptuales": [
            "reportes que nadie lee",
            "decisiones por intuición",
            "datos que nadie confía",
            "información existe pero no se usa"
        ],
        "dimension_primaria": "datos",
        "dimensiones_secundarias": ["cultura", "liderazgo"],
        "impacto_idd": "alto"
    },
    {
        "id": "transformacion_sin_brujula",
        "nombre": "Transformación sin Brújula",
        "descripcion": (
            "Múltiples proyectos digitales corriendo simultáneamente sin coordinación estratégica. "
            "Cada departamento persigue su propia agenda digital."
        ),
        "prevalencia": ">70% de diagnósticos InnoVerse",
        "raiz_causal": "estrategia_gobernanza",
        "no_es": "señal de actividad digital saludable",
        "riesgo_principal": (
            "Recursos dispersos, sin impacto acumulativo, agotamiento del equipo. "
            "La organización termina más confundida que antes."
        ),
        "señales_textuales": [
            r"muchos\s+proyectos\s+(simultáneos|al\s+mismo\s+tiempo|corriendo)",
            r"cada\s+(área|departamento)\s+(tiene\s+su|hace\s+su)\s+proyecto",
            r"sin\s+coordinación", r"sin\s+estrategia\s+(clara|común|unificada)",
            r"proyectos\s+desconectados", r"iniciativas\s+paralelas",
            r"no\s+sabemos\s+(cuál\s+es\s+la\s+prioridad|qué\s+priorizar)",
            r"múltiples\s+(proyectos|iniciativas)\s+digitales"
        ],
        "señales_conceptuales": [
            "muchos proyectos sin dirección",
            "sin priorización estratégica",
            "proyectos sin coordinación",
            "cada área su propia agenda digital"
        ],
        "dimension_primaria": "estrategia",
        "dimensiones_secundarias": ["liderazgo", "procesos"],
        "impacto_idd": "alto"
    }
]


def detectar_antipatrones(
    texto_evidencia: str,
    umbral_confianza: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Detecta anti-patrones en texto de evidencia diagnóstica.

    Args:
        texto_evidencia: Texto libre (transcripciones, notas, respuestas de cuestionario).
        umbral_confianza: Proporción mínima de señales encontradas para confirmar anti-patrón.
                          0.5 = al menos 50% de las señales textuales deben aparecer.

    Returns:
        Lista de anti-patrones detectados, ordenados por confianza descendente.
        Incluye nombre, riesgo, dimensión y evidencia textual encontrada.
    """
    texto_lower = texto_evidencia.lower()
    detectados = []

    for ap in CATALOGO_ANTIPATRONES:
        señales_encontradas = []
        total_señales = len(ap["señales_textuales"])

        for patron in ap["señales_textuales"]:
            try:
                if re.search(patron, texto_lower, re.IGNORECASE | re.MULTILINE):
                    señales_encontradas.append(patron)
            except re.error:
                pass  # Patron inválido, ignorar

        if total_señales > 0:
            confianza = len(señales_encontradas) / total_señales
        else:
            confianza = 0

        if confianza >= umbral_confianza or len(señales_encontradas) >= 2:
            detectados.append({
                "id": ap["id"],
                "nombre": ap["nombre"],
                "confianza": round(confianza, 2),
                "señales_encontradas": len(señales_encontradas),
                "descripcion": ap["descripcion"],
                "riesgo_principal": ap["riesgo_principal"],
                "raiz_causal": ap["raiz_causal"],
                "no_es": ap["no_es"],
                "dimension_primaria": ap["dimension_primaria"],
                "dimensiones_secundarias": ap["dimensiones_secundarias"],
                "impacto_idd": ap["impacto_idd"],
                "prevalencia": ap["prevalencia"]
            })

    # Ordena por confianza descendente, luego por impacto
    orden_impacto = {"crítico": 3, "alto": 2, "medio": 1}
    detectados.sort(
        key=lambda x: (x["confianza"], orden_impacto.get(x["impacto_idd"], 0)),
        reverse=True
    )

    return detectados


def listar_todos() -> List[Dict[str, str]]:
    """Retorna catálogo completo de anti-patrones para referencia."""
    return [
        {
            "id": ap["id"],
            "nombre": ap["nombre"],
            "dimension_primaria": ap["dimension_primaria"],
            "prevalencia": ap["prevalencia"],
            "impacto_idd": ap["impacto_idd"]
        }
        for ap in CATALOGO_ANTIPATRONES
    ]


def get_antipatron(antipatron_id: str) -> Dict:
    """Retorna información completa de un anti-patrón por su ID."""
    for ap in CATALOGO_ANTIPATRONES:
        if ap["id"] == antipatron_id:
            return ap
    raise ValueError(f"Anti-patrón no encontrado: {antipatron_id}")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "listar":
            print("\nCATÁLOGO DE ANTI-PATRONES INNOVERSE:")
            print("=" * 60)
            for ap in listar_todos():
                print(f"  [{ap['id']:25}] {ap['nombre']}")
                print(f"   Dimensión: {ap['dimension_primaria']} | Impacto: {ap['impacto_idd']} | Prevalencia: {ap['prevalencia']}")
                print()
        elif sys.argv[1] == "analizar":
            texto = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else input("Ingresa el texto a analizar: ")
            resultados = detectar_antipatrones(texto)
            if resultados:
                print(f"\nANTI-PATRONES DETECTADOS ({len(resultados)}):")
                print("=" * 60)
                for r in resultados:
                    print(f"\n◆ {r['nombre']} (confianza: {r['confianza']:.0%})")
                    print(f"  Dimensión: {r['dimension_primaria']} | Impacto IDD: {r['impacto_idd']}")
                    print(f"  Riesgo: {r['riesgo_principal']}")
            else:
                print("\nNo se detectaron anti-patrones con el umbral actual.")
    else:
        # Demo
        texto_demo = """
        El director aprueba todas las compras. Cada departamento tiene su propio Excel.
        Compramos un sistema ERP hace 3 años pero solo usamos el 20%.
        En reuniones todos dicen sí pero nadie usa el sistema nuevo.
        """
        print("DEMO — Análisis de texto de ejemplo:")
        print(f"Texto: {texto_demo.strip()}\n")
        resultados = detectar_antipatrones(texto_demo)
        for r in resultados:
            print(f"✓ {r['nombre']} ({r['confianza']:.0%} confianza) — Impacto: {r['impacto_idd']}")
