"""
teams_bot/app.py
=================
Servidor aiohttp que recibe webhooks del Bot Framework de Azure.

Expone un único endpoint:
  POST /api/messages  ← Azure Bot Service envía todas las actividades aquí

Arrancar en desarrollo:
  python -m teams_bot.app

En Azure App Service el host/port lo gestiona la plataforma;
se lee de la variable BOT_PORT (default 3978).

Endpoint de salud para Azure:
  GET /health
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity

# Asegura que el root del proyecto esté en sys.path cuando se ejecuta
# como módulo desde cualquier directorio.
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from teams_bot.bot import DiagnostiCoreBot
from teams_bot.config import CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Bot Framework adapter ──────────────────────────────────────────────────

_settings = BotFrameworkAdapterSettings(
    app_id=CONFIG.app_id,
    app_password=CONFIG.app_password,
    channel_auth_tenant=CONFIG.tenant_id,  # Single Tenant — requerido
)
_adapter = BotFrameworkAdapter(_settings)
_bot = DiagnostiCoreBot()


async def _on_error(context, error: Exception) -> None:
    """Handler global de errores del adapter."""
    logger.exception("BotFrameworkAdapter error: %s", error)
    await context.send_activity("Lo siento, ocurrió un error interno. Intenta de nuevo.")


_adapter.on_turn_error = _on_error


# ── Endpoints ──────────────────────────────────────────────────────────────

async def messages(req: Request) -> Response:
    """
    POST /api/messages
    Azure Bot Service envía todas las actividades (mensajes, events,
    card submits, etc.) a este endpoint como JSON firmado con las
    credenciales del bot.
    """
    if "application/json" not in req.content_type:
        return Response(status=415, text="Content-Type must be application/json")

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    async def call_bot(turn_context):
        await _bot.on_turn(turn_context)

    try:
        await _adapter.process_activity(activity, auth_header, call_bot)
    except Exception as exc:
        logger.exception("process_activity failed: %s", exc)
        return Response(status=500, text=str(exc))

    return Response(status=200)


async def health(_req: Request) -> Response:
    """GET /health — usado por Azure para liveness checks."""
    return json_response({"status": "ok", "app_id": CONFIG.app_id})


# ── App factory ────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/health", health)
    return app


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    CONFIG.validate()
    logger.info(
        "DiagnostiCore Teams Bot arrancando en puerto %d | App ID: %s",
        CONFIG.port,
        CONFIG.app_id,
    )
    web.run_app(create_app(), host="0.0.0.0", port=CONFIG.port)
