"""
DiagnostiCore — Cuantificador de Costo de Inacción (Cost of Delay)
==================================================================
Calcula el costo mensual y anual del status quo con factores de
conservadurismo InnoVerse (70% reducción costo / 50% aumento revenue).

Uso:
    from tools.cuantificar_costo import CuantificadorCosto

    calc = CuantificadorCosto()

    # Agregar componentes de costo
    calc.agregar_ineficiencia_proceso(
        nombre="Reportes manuales de ventas",
        horas_mes=40,
        costo_hora_mxn=200,
        factor_ineficiencia=1.3
    )
    calc.agregar_revenue_perdido(
        nombre="Clientes perdidos por falta de seguimiento CRM",
        monto_mensual_mxn=50000
    )

    resultado = calc.calcular()
    print(resultado["resumen"])
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json


# Factores de conservadurismo InnoVerse
FACTOR_REDUCCION_COSTO = 0.70   # Proyección de ahorro × 70%
FACTOR_AUMENTO_REVENUE = 0.50   # Proyección de revenue × 50%


@dataclass
class ComponenteCosto:
    nombre: str
    tipo: str  # "ineficiencia_proceso" | "revenue_perdido" | "riesgo" | "costo_oculto"
    monto_mensual_bruto: float
    descripcion: str = ""
    dimension_origen: str = ""
    evidencia: str = ""


class CuantificadorCosto:
    """
    Calcula el costo mensual de inacción aplicando los factores
    de conservadurismo estándar de InnoVerse.
    """

    def __init__(self, nombre_cliente: str = ""):
        self.nombre_cliente = nombre_cliente
        self._componentes: List[ComponenteCosto] = []

    def agregar_ineficiencia_proceso(
        self,
        nombre: str,
        horas_mes: float,
        costo_hora_mxn: float,
        factor_ineficiencia: float = 1.0,
        descripcion: str = "",
        dimension_origen: str = "procesos",
        evidencia: str = ""
    ) -> "CuantificadorCosto":
        """
        Agrega costo por proceso manual/ineficiente.

        Args:
            horas_mes: Horas dedicadas al proceso por mes
            costo_hora_mxn: Costo promedio por hora en MXN (incluye prestaciones)
            factor_ineficiencia: Multiplicador de ineficiencia (1.0=ninguna, 1.5=50% más lento)
        """
        monto = horas_mes * costo_hora_mxn * factor_ineficiencia
        self._componentes.append(ComponenteCosto(
            nombre=nombre,
            tipo="ineficiencia_proceso",
            monto_mensual_bruto=monto,
            descripcion=descripcion or f"{horas_mes}h/mes × ${costo_hora_mxn}/h × {factor_ineficiencia}x",
            dimension_origen=dimension_origen,
            evidencia=evidencia
        ))
        return self

    def agregar_revenue_perdido(
        self,
        nombre: str,
        monto_mensual_mxn: float,
        descripcion: str = "",
        dimension_origen: str = "datos",
        evidencia: str = ""
    ) -> "CuantificadorCosto":
        """
        Agrega oportunidad de revenue perdido (pipeline no convertido, clientes no retenidos, etc.)
        Se aplica factor conservador del 50%.
        """
        self._componentes.append(ComponenteCosto(
            nombre=nombre,
            tipo="revenue_perdido",
            monto_mensual_bruto=monto_mensual_mxn,
            descripcion=descripcion,
            dimension_origen=dimension_origen,
            evidencia=evidencia
        ))
        return self

    def agregar_costo_riesgo(
        self,
        nombre: str,
        probabilidad_mensual: float,
        impacto_mxn: float,
        descripcion: str = "",
        dimension_origen: str = "tecnologia",
        evidencia: str = ""
    ) -> "CuantificadorCosto":
        """
        Agrega riesgo como costo esperado (probabilidad × impacto).
        Se reporta como escenario, no como costo fijo.
        """
        monto_esperado = probabilidad_mensual * impacto_mxn
        self._componentes.append(ComponenteCosto(
            nombre=nombre,
            tipo="riesgo",
            monto_mensual_bruto=monto_esperado,
            descripcion=descripcion or f"P={probabilidad_mensual:.0%} × ${impacto_mxn:,.0f}",
            dimension_origen=dimension_origen,
            evidencia=evidencia
        ))
        return self

    def agregar_costo_oculto(
        self,
        nombre: str,
        monto_mensual_mxn: float,
        descripcion: str = "",
        dimension_origen: str = "",
        evidencia: str = ""
    ) -> "CuantificadorCosto":
        """
        Agrega costo oculto directo (licencias sin usar, expediciones de emergencia, retrabajos).
        """
        self._componentes.append(ComponenteCosto(
            nombre=nombre,
            tipo="costo_oculto",
            monto_mensual_bruto=monto_mensual_mxn,
            descripcion=descripcion,
            dimension_origen=dimension_origen,
            evidencia=evidencia
        ))
        return self

    def calcular(self) -> Dict[str, Any]:
        """
        Calcula el costo total con factores de conservadurismo aplicados.

        Returns:
            Diccionario con totales, desglose por tipo, y textos de resumen.
        """
        if not self._componentes:
            raise ValueError("No hay componentes de costo agregados. Use los métodos agregar_*() primero.")

        desglose = []
        total_conservador = 0.0
        total_bruto = 0.0

        # Aplica factores por tipo
        factores = {
            "ineficiencia_proceso": FACTOR_REDUCCION_COSTO,
            "costo_oculto": FACTOR_REDUCCION_COSTO,
            "revenue_perdido": FACTOR_AUMENTO_REVENUE,
            "riesgo": 1.0  # Los riesgos se reportan como escenario, sin factor adicional
        }

        for comp in self._componentes:
            factor = factores.get(comp.tipo, FACTOR_REDUCCION_COSTO)
            monto_conservador = comp.monto_mensual_bruto * factor

            total_bruto += comp.monto_mensual_bruto
            total_conservador += monto_conservador

            desglose.append({
                "nombre": comp.nombre,
                "tipo": comp.tipo,
                "monto_bruto_mensual": round(comp.monto_mensual_bruto, 2),
                "factor_conservadurismo": f"{factor:.0%}",
                "monto_conservador_mensual": round(monto_conservador, 2),
                "descripcion": comp.descripcion,
                "dimension_origen": comp.dimension_origen,
                "evidencia": comp.evidencia
            })

        total_anual = total_conservador * 12

        return {
            "cliente": self.nombre_cliente,
            "costo_mensual_mxn": round(total_conservador, 2),
            "costo_anual_mxn": round(total_anual, 2),
            "costo_mensual_formateado": _formatear_mxn(total_conservador),
            "costo_anual_formateado": _formatear_mxn(total_anual),
            "desglose": desglose,
            "nota_metodologica": (
                f"Estimaciones con factores de conservadurismo InnoVerse: "
                f"reducción de costo ×{FACTOR_REDUCCION_COSTO:.0%}, "
                f"aumento de revenue ×{FACTOR_AUMENTO_REVENUE:.0%}. "
                f"Total bruto proyectado: {_formatear_mxn(total_bruto)}/mes."
            ),
            "resumen": _generar_resumen(total_conservador, total_anual, desglose),
            "desglose_texto": _generar_desglose_texto(desglose)
        }

    def desde_json(self, datos: Dict) -> "CuantificadorCosto":
        """Carga componentes desde un diccionario JSON."""
        for comp in datos.get("componentes", []):
            tipo = comp.get("tipo", "costo_oculto")
            if tipo == "ineficiencia_proceso":
                self.agregar_costo_oculto(
                    nombre=comp["nombre"],
                    monto_mensual_mxn=comp["monto_mensual_bruto"],
                    descripcion=comp.get("descripcion", ""),
                    dimension_origen=comp.get("dimension_origen", ""),
                    evidencia=comp.get("evidencia", "")
                )
            elif tipo == "revenue_perdido":
                self.agregar_revenue_perdido(
                    nombre=comp["nombre"],
                    monto_mensual_mxn=comp["monto_mensual_bruto"],
                    descripcion=comp.get("descripcion", ""),
                    dimension_origen=comp.get("dimension_origen", ""),
                    evidencia=comp.get("evidencia", "")
                )
            else:
                self.agregar_costo_oculto(
                    nombre=comp["nombre"],
                    monto_mensual_mxn=comp["monto_mensual_bruto"],
                    descripcion=comp.get("descripcion", ""),
                    dimension_origen=comp.get("dimension_origen", ""),
                    evidencia=comp.get("evidencia", "")
                )
        return self


def _formatear_mxn(monto: float) -> str:
    """Formatea número como moneda MXN."""
    if monto >= 1_000_000:
        return f"${monto/1_000_000:.1f}M MXN"
    elif monto >= 1_000:
        return f"${monto:,.0f} MXN"
    return f"${monto:.0f} MXN"


def _generar_resumen(mensual: float, anual: float, desglose: List[Dict]) -> str:
    componente_mayor = max(desglose, key=lambda x: x["monto_conservador_mensual"])
    return (
        f"Costo mensual de inacción: {_formatear_mxn(mensual)} "
        f"({_formatear_mxn(anual)}/año). "
        f"Componente principal: {componente_mayor['nombre']} "
        f"({_formatear_mxn(componente_mayor['monto_conservador_mensual'])}/mes)."
    )


def _generar_desglose_texto(desglose: List[Dict]) -> str:
    """Genera texto de desglose para el One-Pager."""
    lineas = []
    for item in desglose:
        tipo_label = {
            "ineficiencia_proceso": "Ineficiencia",
            "revenue_perdido": "Revenue perdido",
            "riesgo": "Riesgo",
            "costo_oculto": "Costo oculto"
        }.get(item["tipo"], item["tipo"])

        lineas.append(
            f"• {item['nombre']} [{tipo_label}]: "
            f"{_formatear_mxn(item['monto_conservador_mensual'])}/mes"
        )
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────
# CLI / Demo
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Demo con datos del caso CompoLat del Book 360
    print("DEMO — Cuantificación Costo de Inacción: CompoLat")
    print("=" * 55)

    calc = CuantificadorCosto("CompoLat")

    calc.agregar_ineficiencia_proceso(
        nombre="Planificación de producción manual",
        horas_mes=80,
        costo_hora_mxn=300,
        factor_ineficiencia=1.4,
        descripcion="Actualización semanal en hojas de cálculo. 2 personas × 40h/mes",
        dimension_origen="procesos",
        evidencia="Transcripción jefe de producción: 'Actualizamos el Excel cada viernes'"
    )

    calc.agregar_costo_oculto(
        nombre="Expediciones de emergencia por falta de integración Ventas-Producción",
        monto_mensual_mxn=18000,
        descripcion="Promedio 6 expediciones × $3,000 costo adicional por expedición",
        dimension_origen="procesos",
        evidencia="Contabilidad reportó 68 expediciones en los últimos 12 meses"
    )

    calc.agregar_revenue_perdido(
        nombre="Clientes perdidos por tiempos de respuesta lentos",
        monto_mensual_mxn=45000,
        descripcion="3-4 oportunidades/mes × $15,000 ticket promedio",
        dimension_origen="datos",
        evidencia="Ventas: 'Perdemos contratos porque tardamos 2 semanas en cotizar'"
    )

    resultado = calc.calcular()

    print(f"\n{resultado['resumen']}\n")
    print("DESGLOSE:")
    print(resultado["desglose_texto"])
    print(f"\n{resultado['nota_metodologica']}")
