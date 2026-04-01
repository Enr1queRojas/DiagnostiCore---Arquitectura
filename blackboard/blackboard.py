"""
DiagnostiCore Blackboard Manager
=================================
Sistema de estado compartido entre todos los sub-agentes del Diagnóstico 360.

Uso:
    from blackboard.blackboard import Blackboard

    # Leer estado actual
    bb = Blackboard("runs/COMPOLAT_20260330.json")
    estado = bb.get_estado()
    evidencia = bb.get_evidencia()

    # Escribir resultado de un agente
    bb.write_resultado_dimensional("A1_estrategia", {
        "nivel_madurez": 2,
        "justificacion": "...",
        "hallazgos_principales": ["h1", "h2", "h3"],
        "antipatrones_detectados": ["excel_sagrado"],
        "traduccion_negocio": "...",
        "senal_alerta_critica": "..."
    })

    # Avanzar estado del run
    bb.set_estado("analisis_dimensional")
    bb.marcar_agente_completado("A1")
"""

import asyncio
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List


ESTADOS_VALIDOS = [
    "iniciado",
    "levantamiento",
    "analisis_dimensional",
    "sintesis",
    "output",
    "completado",
    "error"
]

AGENTES_VALIDOS = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]

DIMENSIONES_VALIDAS = [
    "A1_estrategia",
    "A2_liderazgo",
    "A3_cultura",
    "A4_procesos",
    "A5_datos",
    "A6_tecnologia"
]

ANTIPATRONES_VALIDOS = [
    "excel_sagrado",
    "director_orquesta",
    "isla_automatizacion",
    "resistencia_silenciosa",
    "erp_fantasma",
    "datos_no_hablan",
    "transformacion_sin_brujula"
]


class BlackboardError(Exception):
    """Error del sistema de blackboard."""
    pass


class Blackboard:
    """
    Gestor del estado compartido del diagnóstico.
    Thread-safe para uso en sistemas agénticos paralelos.
    """

    def __init__(self, run_path: str):
        """
        Inicializa el blackboard desde un archivo de run.

        Args:
            run_path: Ruta al archivo JSON del run activo.
                      Ejemplo: "runs/COMPOLAT_20260330.json"
        """
        self.run_path = Path(run_path)
        if not self.run_path.exists():
            raise BlackboardError(
                f"Archivo de run no encontrado: {run_path}\n"
                f"Crea un nuevo run con: Blackboard.crear_run('CLIENTE', 'sector')"
            )
        self._data = self._cargar()
        # Lazy-initialised asyncio.Lock — guards concurrent write_* calls when
        # agents run in parallel (Fase 3+). Lazy init avoids binding the lock
        # to an event loop at construction time (Blackboard may be created in
        # synchronous code such as crear_run()).
        self._write_lock_instance: asyncio.Lock | None = None

    @property
    def write_lock(self) -> asyncio.Lock:
        """
        Asyncio lock that serialises all blackboard write operations.

        Acquiring this lock before calling any write_* method ensures that
        parallel agents (asyncio.gather) cannot produce a torn write —
        i.e. two agents simultaneously modifying self._data before _guardar()
        completes.

        Note: In CPython asyncio (single-threaded), write_* methods that
        contain no internal await points are already de-facto atomic.
        This lock provides an explicit contract and a safe upgrade path to
        multi-thread or multi-process execution in Fase 4.
        """
        if self._write_lock_instance is None:
            self._write_lock_instance = asyncio.Lock()
        return self._write_lock_instance

    # ─────────────────────────────────────────────────────────
    # MÉTODOS DE FÁBRICA
    # ─────────────────────────────────────────────────────────

    @classmethod
    def crear_run(
        cls,
        nombre_cliente: str,
        sector: str,
        consultor: str,
        tamaño: str = "mediana",
        empleados: int = 0,
        anos_operacion: int = 0,
        pais: str = "México",
        runs_dir: str = "runs"
    ) -> "Blackboard":
        """
        Crea un nuevo run de diagnóstico desde el template.

        Returns:
            Instancia de Blackboard lista para usar.
        """
        # Genera run_id
        fecha = datetime.now().strftime("%Y%m%d")
        slug = nombre_cliente.upper().replace(" ", "")[:12]
        run_id = f"{slug}_{fecha}"
        run_path = Path(runs_dir) / f"{run_id}.json"

        # Carga template
        template_path = Path(__file__).parent / "template.json"
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Rellena datos
        data.pop("_instrucciones", None)
        data["run_id"] = run_id
        data["estado"] = "iniciado"
        data["cliente"] = {
            "nombre": nombre_cliente,
            "sector": sector,
            "tamaño": tamaño,
            "empleados": empleados,
            "anos_operacion": anos_operacion,
            "pais": pais,
            "consultor_responsable": consultor,
            "fecha_inicio": datetime.now().strftime("%Y-%m-%d")
        }
        data["timestamps"]["iniciado"] = cls._now()

        # Guarda
        Path(runs_dir).mkdir(exist_ok=True)
        with open(run_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✓ Run creado: {run_path}")
        return cls(str(run_path))

    # ─────────────────────────────────────────────────────────
    # LECTURA
    # ─────────────────────────────────────────────────────────

    def get_estado(self) -> str:
        return self._data["estado"]

    def get_cliente(self) -> Dict[str, Any]:
        return self._data["cliente"]

    def get_evidencia(self) -> Dict[str, Any]:
        return self._data.get("evidencia", {})

    def get_resultado_dimensional(self, dimension: str) -> Optional[Dict]:
        """Obtiene el resultado de un agente dimensional (A1–A6)."""
        if dimension not in DIMENSIONES_VALIDAS:
            raise BlackboardError(f"Dimensión inválida: {dimension}. Válidas: {DIMENSIONES_VALIDAS}")
        return self._data["resultados_dimensionales"].get(dimension)

    def get_todos_resultados_dimensionales(self) -> Dict[str, Any]:
        return self._data["resultados_dimensionales"]

    def get_sintesis(self) -> Optional[Dict]:
        return self._data.get("sintesis")

    def get_one_pager(self) -> Optional[Dict]:
        return self._data.get("one_pager")

    def agentes_completados(self) -> List[str]:
        return self._data["metadatos"]["agentes_completados"]

    def todos_dimensionales_completos(self) -> bool:
        """Retorna True si A1–A6 completaron su análisis."""
        for dim in DIMENSIONES_VALIDAS:
            if self._data["resultados_dimensionales"].get(dim) is None:
                return False
        return True

    def resumen_estado(self) -> str:
        """Retorna un resumen legible del estado del run."""
        cliente = self._data["cliente"]["nombre"]
        estado = self._data["estado"]
        completados = self._data["metadatos"]["agentes_completados"]
        pendientes = [a for a in AGENTES_VALIDOS if a not in completados]

        return (
            f"Run: {self._data['run_id']}\n"
            f"Cliente: {cliente}\n"
            f"Estado: {estado}\n"
            f"Agentes completados: {completados or 'Ninguno'}\n"
            f"Agentes pendientes: {pendientes}\n"
        )

    # ─────────────────────────────────────────────────────────
    # ESCRITURA
    # ─────────────────────────────────────────────────────────

    def set_estado(self, estado: str) -> None:
        if estado not in ESTADOS_VALIDOS:
            raise BlackboardError(f"Estado inválido: {estado}. Válidos: {ESTADOS_VALIDOS}")
        self._data["estado"] = estado
        self._guardar()

    def add_evidencia_transcripcion(self, entrevistado_rol: str, texto: str,
                                     dimension_primaria: str = "") -> None:
        transcripcion = {
            "entrevistado_rol": entrevistado_rol,
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "texto": texto,
            "dimension_primaria": dimension_primaria
        }
        self._data["evidencia"]["transcripciones"].append(transcripcion)
        self._guardar()

    def write_resultado_dimensional(self, dimension: str, resultado: Dict[str, Any]) -> None:
        """
        Escribe el resultado de un agente dimensional en el blackboard.

        Args:
            dimension: Una de las DIMENSIONES_VALIDAS (ej: "A1_estrategia")
            resultado: Dict con nivel_madurez, justificacion, hallazgos_principales, etc.
        """
        if dimension not in DIMENSIONES_VALIDAS:
            raise BlackboardError(f"Dimensión inválida: {dimension}")

        # Valida campos requeridos
        required = ["nivel_madurez", "justificacion", "hallazgos_principales"]
        for campo in required:
            if campo not in resultado:
                raise BlackboardError(f"Campo requerido faltante en resultado: {campo}")

        # Valida nivel de madurez
        nivel = resultado["nivel_madurez"]
        if not isinstance(nivel, int) or not (1 <= nivel <= 5):
            raise BlackboardError(f"nivel_madurez debe ser entero entre 1 y 5. Recibido: {nivel}")

        # Valida anti-patrones
        antipatrones = resultado.get("antipatrones_detectados", [])
        for ap in antipatrones:
            if ap not in ANTIPATRONES_VALIDOS:
                raise BlackboardError(f"Anti-patrón inválido: {ap}. Válidos: {ANTIPATRONES_VALIDOS}")

        # Escribe
        self._data["resultados_dimensionales"][dimension] = resultado

        # Marca timestamp y agente como completado
        agente_id = dimension.split("_")[0].upper()  # "A1_estrategia" → "A1"
        self._data["timestamps"][f"{agente_id}_completado"] = self._now()
        self.marcar_agente_completado(agente_id)

        self._guardar()
        print(f"✓ {dimension}: Nivel {nivel}/5 registrado en blackboard")

    def write_sintesis(self, sintesis: Dict[str, Any]) -> None:
        """Escribe el output del agente A7 (Motor de Síntesis)."""
        if not self.todos_dimensionales_completos():
            raise BlackboardError(
                "No se puede escribir síntesis: hay agentes dimensionales pendientes.\n"
                f"Estado: {self.resumen_estado()}"
            )

        # Valida causas raíz
        causas = sintesis.get("causas_raiz", [])
        if len(causas) > 3:
            raise BlackboardError(
                f"REGLA VIOLADA: Máximo 3 causas raíz permitidas. "
                f"Se intentaron escribir {len(causas)}.\n"
                f"Profundiza el análisis causal para consolidar."
            )
        if len(causas) == 0:
            raise BlackboardError("La síntesis debe incluir al menos 1 causa raíz.")

        # Valida IDD
        idd = sintesis.get("idd")
        if idd is not None and not (0 <= idd <= 100):
            raise BlackboardError(f"IDD debe estar entre 0 y 100. Recibido: {idd}")

        self._data["sintesis"] = sintesis
        self._data["timestamps"]["A7_completado"] = self._now()
        self.marcar_agente_completado("A7")
        self._guardar()
        print(f"✓ Síntesis registrada. IDD: {idd}/100. Causas raíz: {len(causas)}")

    def write_one_pager(self, one_pager: Dict[str, Any]) -> None:
        """Escribe el output final del agente A8."""
        if self._data.get("sintesis") is None:
            raise BlackboardError("No se puede generar One-Pager sin síntesis completada.")

        self._data["one_pager"] = one_pager
        self._data["timestamps"]["A8_completado"] = self._now()
        self._data["estado"] = "completado"
        self.marcar_agente_completado("A8")
        self._guardar()
        print(f"✓ One-Pager generado. Run completado: {self._data['run_id']}")

    def marcar_agente_completado(self, agente: str) -> None:
        if agente not in AGENTES_VALIDOS:
            raise BlackboardError(f"Agente inválido: {agente}")
        completados = self._data["metadatos"]["agentes_completados"]
        if agente not in completados:
            completados.append(agente)
        self._guardar()

    def registrar_error(self, agente: str, mensaje: str) -> None:
        error = {
            "agente": agente,
            "mensaje": mensaje,
            "timestamp": self._now()
        }
        self._data["metadatos"]["errores"].append(error)
        self._data["estado"] = "error"
        self._guardar()
        print(f"⚠ Error registrado en {agente}: {mensaje}")

    def agregar_nota_consultor(self, nota: str) -> None:
        existente = self._data["metadatos"].get("notas_consultor", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._data["metadatos"]["notas_consultor"] = (
            f"{existente}\n[{timestamp}] {nota}" if existente else f"[{timestamp}] {nota}"
        )
        self._guardar()

    # ─────────────────────────────────────────────────────────
    # UTILIDADES
    # ─────────────────────────────────────────────────────────

    def exportar_para_agente(self, agente_id: str) -> Dict[str, Any]:
        """
        Retorna solo la información relevante para un agente específico.
        Minimiza el contexto que cada agente necesita procesar.
        """
        base = {
            "run_id": self._data["run_id"],
            "cliente": self._data["cliente"],
            "estado": self._data["estado"]
        }

        # Agentes dimensionales (A1–A6): necesitan la evidencia
        if agente_id in ["A1","A2","A3","A4","A5","A6"]:
            base["evidencia"] = self._data["evidencia"]

        # A7 necesita todos los resultados dimensionales
        elif agente_id == "A7":
            base["resultados_dimensionales"] = self._data["resultados_dimensionales"]

        # A8 necesita la síntesis
        elif agente_id == "A8":
            base["sintesis"] = self._data["sintesis"]
            base["cliente"] = self._data["cliente"]

        return base

    def to_markdown_resumen(self) -> str:
        """Genera un resumen markdown del estado actual del run."""
        d = self._data
        cliente = d["cliente"]["nombre"]
        estado = d["estado"]

        lines = [
            f"# DiagnostiCore — Run: {d['run_id']}",
            f"**Cliente:** {cliente} | **Estado:** {estado}",
            f"**Consultor:** {d['cliente'].get('consultor_responsable', 'N/D')}",
            "",
            "## Estado de Agentes",
            "| Agente | Dimensión | Estado |",
            "|--------|-----------|--------|"
        ]

        agentes_info = [
            ("A1", "Estrategia", "A1_estrategia"),
            ("A2", "Liderazgo",  "A2_liderazgo"),
            ("A3", "Cultura",    "A3_cultura"),
            ("A4", "Procesos",   "A4_procesos"),
            ("A5", "Datos",      "A5_datos"),
            ("A6", "Tecnología", "A6_tecnologia"),
            ("A7", "Síntesis",   None),
            ("A8", "One-Pager",  None),
        ]

        completados = d["metadatos"]["agentes_completados"]
        for agente_id, dim, dim_key in agentes_info:
            status = "✅ Completado" if agente_id in completados else "⏳ Pendiente"
            if dim_key and d["resultados_dimensionales"].get(dim_key):
                nivel = d["resultados_dimensionales"][dim_key].get("nivel_madurez", "?")
                status += f" (Nivel {nivel}/5)"
            lines.append(f"| {agente_id} | {dim} | {status} |")

        # IDD si disponible
        if d.get("sintesis"):
            idd = d["sintesis"].get("idd", "N/D")
            lines.append("")
            lines.append(f"## Índice de Deuda Digital: **{idd}/100**")

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────
    # PRIVADOS
    # ─────────────────────────────────────────────────────────

    def _cargar(self) -> Dict[str, Any]:
        with open(self.run_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _guardar(self) -> None:
        # Escritura atómica: escribe en .tmp luego renombra
        tmp_path = self.run_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self.run_path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────
# CLI RÁPIDA
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso:")
        print("  python blackboard.py status runs/CLIENTE.json")
        print("  python blackboard.py nuevo 'NombreCliente' sector consultor [runs/]")
        sys.exit(1)

    comando = sys.argv[1]

    if comando == "status" and len(sys.argv) >= 3:
        bb = Blackboard(sys.argv[2])
        print(bb.to_markdown_resumen())

    elif comando == "nuevo" and len(sys.argv) >= 5:
        nombre = sys.argv[2]
        sector = sys.argv[3]
        consultor = sys.argv[4]
        runs_dir = sys.argv[5] if len(sys.argv) > 5 else "runs"
        bb = Blackboard.crear_run(nombre, sector, consultor, runs_dir=runs_dir)
        print(bb.to_markdown_resumen())

    else:
        print(f"Comando no reconocido: {comando}")
        sys.exit(1)
