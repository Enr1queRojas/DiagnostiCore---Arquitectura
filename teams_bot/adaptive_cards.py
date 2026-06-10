"""
teams_bot/adaptive_cards.py
=============================
Adaptive Cards v1.5 para el bot de DiagnostiCore en Teams.

Cada función devuelve un dict serializable a JSON que se pasa a
Attachment(content_type="application/vnd.microsoft.card.adaptive", content=...).
"""
from __future__ import annotations

# ── Paleta InnoVerse ──────────────────────────────────────────────────────
_MAGENTA = "#A3195B"
_DARK = "#1C1C1E"
_ORANGE = "#E94E1B"
_LIGHT_BG = "#F9F5FB"


def welcome_card() -> dict:
    """Card de bienvenida mostrada cuando el bot se instala en un canal."""
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "Container",
                "style": "emphasis",
                "bleed": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "DiagnostiCore",
                        "size": "ExtraLarge",
                        "weight": "Bolder",
                        "color": "Light",
                    },
                    {
                        "type": "TextBlock",
                        "text": "Sistema Agéntico de Diagnóstico 360 — InnoVerse Solutions",
                        "color": "Light",
                        "wrap": True,
                        "spacing": "None",
                    },
                ],
                "backgroundColor": _DARK,
            },
            {
                "type": "TextBlock",
                "text": "**Comandos disponibles:**",
                "wrap": True,
                "spacing": "Medium",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "nuevo", "value": "Iniciar un nuevo diagnóstico"},
                    {"title": "estado [run_id]", "value": "Ver progreso de un diagnóstico"},
                    {"title": "reporte [run_id]", "value": "Obtener el reporte final"},
                    {"title": "ayuda", "value": "Mostrar esta pantalla"},
                ],
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Nuevo diagnóstico",
                "style": "positive",
                "data": {"action": "show_new_run_form"},
            }
        ],
    }


def new_run_form_card() -> dict:
    """Formulario para capturar los datos del cliente antes de crear el run."""
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Nuevo Diagnóstico 360",
                "size": "Large",
                "weight": "Bolder",
                "color": "Accent",
            },
            {
                "type": "TextBlock",
                "text": "Completa los datos del cliente para iniciar el pipeline.",
                "wrap": True,
                "spacing": "None",
                "isSubtle": True,
            },
            {
                "type": "Input.Text",
                "id": "cliente",
                "label": "Nombre de la empresa",
                "placeholder": "Ej. CompoLat Industrial",
                "isRequired": True,
                "errorMessage": "El nombre del cliente es obligatorio.",
            },
            {
                "type": "Input.ChoiceSet",
                "id": "sector",
                "label": "Sector",
                "isRequired": True,
                "style": "compact",
                "choices": [
                    {"title": "Manufactura", "value": "manufactura"},
                    {"title": "Comercializadora", "value": "comercializadora"},
                    {"title": "Servicios profesionales", "value": "servicios"},
                    {"title": "Inmobiliario", "value": "inmobiliario"},
                    {"title": "Tecnología", "value": "tecnologia"},
                    {"title": "Retail", "value": "retail"},
                    {"title": "Otro", "value": "otro"},
                ],
            },
            {
                "type": "Input.ChoiceSet",
                "id": "tamanio",
                "label": "Tamaño",
                "isRequired": True,
                "style": "compact",
                "choices": [
                    {"title": "Pequeña (< 50 empleados)", "value": "pequena"},
                    {"title": "Mediana (50–500)", "value": "mediana"},
                    {"title": "Grande (> 500)", "value": "grande"},
                ],
            },
            {
                "type": "Input.Number",
                "id": "empleados",
                "label": "Número aproximado de empleados",
                "placeholder": "200",
                "min": 1,
                "isRequired": True,
            },
            {
                "type": "Input.Text",
                "id": "consultor",
                "label": "Consultor responsable",
                "placeholder": "Tu nombre",
                "isRequired": True,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Iniciar diagnóstico",
                "style": "positive",
                "data": {"action": "create_run"},
            },
            {
                "type": "Action.Submit",
                "title": "Cancelar",
                "data": {"action": "cancel"},
            },
        ],
    }


def run_created_card(run_id: str, cliente: str) -> dict:
    """Confirmación de run creado. Incluye botón para iniciar el pipeline."""
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": f"✅ Run creado: **{cliente}**",
                "size": "Medium",
                "weight": "Bolder",
                "wrap": True,
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Run ID", "value": f"`{run_id}`"},
                    {"title": "Estado", "value": "Listo para iniciar"},
                ],
            },
            {
                "type": "TextBlock",
                "text": "Guarda el Run ID — lo necesitarás para consultar el estado y el reporte.",
                "wrap": True,
                "isSubtle": True,
                "spacing": "Small",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "▶ Iniciar pipeline",
                "style": "positive",
                "data": {"action": "start_pipeline", "run_id": run_id},
            }
        ],
    }


def pipeline_started_card(run_id: str) -> dict:
    """Card mostrada cuando el pipeline arranca. Indica cómo monitorear."""
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "⚙️ Pipeline iniciado",
                "size": "Medium",
                "weight": "Bolder",
            },
            {
                "type": "TextBlock",
                "text": (
                    f"El diagnóstico **{run_id}** está corriendo. "
                    "Los agentes A1–A11 analizarán las seis dimensiones, "
                    "generarán la síntesis y producirán el One-Pager y el Reporte Completo."
                ),
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"Escribe `estado {run_id}` en cualquier momento para ver el progreso.",
                "wrap": True,
                "isSubtle": True,
                "spacing": "Small",
            },
        ],
    }


def run_status_card(status: dict) -> dict:
    """Card de estado del pipeline con progreso por agente."""
    run_id = status.get("run_id", "—")
    estado = status.get("estado", "desconocido")
    cliente_info = status.get("cliente", {})
    cliente_nombre = cliente_info.get("nombre", "—") if isinstance(cliente_info, dict) else str(cliente_info)
    idd = status.get("idd")
    agents: list[dict] = status.get("agents", [])

    agent_labels = {
        "A1": "Estrategia", "A2": "Liderazgo", "A3": "Cultura",
        "A4": "Procesos", "A5": "Datos", "A6": "Tecnología",
        "A7": "Síntesis", "A8": "One-Pager",
    }

    facts = []
    for ag in agents:
        aid = ag.get("agent_id", "")
        label = agent_labels.get(aid, aid)
        done = ag.get("completed", False)
        nivel = ag.get("nivel_madurez")
        valor = f"✅ Nivel {nivel}/5" if done and nivel else ("✅ Completado" if done else "⏳ Pendiente")
        facts.append({"title": label, "value": valor})

    body = [
        {
            "type": "TextBlock",
            "text": f"Estado del diagnóstico: **{cliente_nombre}**",
            "size": "Medium",
            "weight": "Bolder",
            "wrap": True,
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Run ID", "value": f"`{run_id}`"},
                {"title": "Estado", "value": estado.upper()},
            ]
            + ([{"title": "IDD", "value": f"{idd}/100"}] if idd is not None else []),
        },
    ]

    if facts:
        body.append({
            "type": "Container",
            "style": "emphasis",
            "items": [
                {"type": "TextBlock", "text": "Progreso por agente", "weight": "Bolder"},
                {"type": "FactSet", "facts": facts},
            ],
            "spacing": "Medium",
        })

    errores: list = status.get("errores", [])
    if errores:
        body.append({
            "type": "TextBlock",
            "text": f"⚠️ {len(errores)} error(es) registrado(s). Consulta los logs.",
            "color": "Warning",
            "wrap": True,
        })

    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": body,
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🔄 Actualizar",
                "data": {"action": "refresh_status", "run_id": run_id},
            }
        ]
        if estado not in ("completado",)
        else [
            {
                "type": "Action.Submit",
                "title": "📄 Ver reporte",
                "style": "positive",
                "data": {"action": "get_report", "run_id": run_id},
            }
        ],
    }


def report_card(report: dict, run_id: str) -> dict:
    """Card del reporte final con IDD, causas raíz y One-Pager."""
    idd = report.get("idd")
    clasificacion = report.get("idd_clasificacion", "")
    causas_n = report.get("causas_raiz_count", 0)
    one_pager = report.get("one_pager_available", False)
    summary = report.get("markdown_summary", "")[:600]  # preview

    idd_color = "Good" if idd and idd >= 60 else ("Warning" if idd and idd >= 40 else "Attention")

    body = [
        {
            "type": "Container",
            "style": "emphasis",
            "bleed": True,
            "items": [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "Diagnóstico completado",
                                    "size": "Large",
                                    "weight": "Bolder",
                                    "color": "Light",
                                }
                            ],
                        },
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"IDD: **{idd}/100**" if idd else "IDD: —",
                                    "size": "Large",
                                    "weight": "Bolder",
                                    "color": idd_color,
                                }
                            ],
                        },
                    ],
                }
            ],
            "backgroundColor": _DARK,
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Clasificación IDD", "value": clasificacion or "—"},
                {"title": "Causas raíz identificadas", "value": str(causas_n)},
                {"title": "One-Pager", "value": "✅ Disponible" if one_pager else "❌ No disponible"},
            ],
            "spacing": "Medium",
        },
    ]

    if summary:
        body.append({
            "type": "TextBlock",
            "text": summary + ("…" if len(report.get("markdown_summary", "")) > 600 else ""),
            "wrap": True,
            "spacing": "Medium",
            "isSubtle": True,
        })

    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": body,
        "actions": [
            {
                "type": "Action.Submit",
                "title": "🔄 Actualizar reporte",
                "data": {"action": "get_report", "run_id": run_id},
            }
        ],
    }


def error_card(message: str) -> dict:
    """Card genérica de error."""
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "⚠️ Error",
                "size": "Medium",
                "weight": "Bolder",
                "color": "Attention",
            },
            {
                "type": "TextBlock",
                "text": message,
                "wrap": True,
            },
        ],
    }
