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

import logging
import sys
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response, json_response

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

# ── Bot Framework adapter (Single Tenant) ─────────────────────────────────
#
# BotFrameworkAdapterSettings.channel_auth_tenant configura la validación
# de tokens ENTRANTES pero no propaga el tenant a las credenciales de
# SALIDA en todas las versiones del SDK.
#
# Solución: usar ConfigurationBotFrameworkAuthentication + CloudAdapter,
# que maneja Single/Multi-Tenant y MSI correctamente.

try:
    from botbuilder.integration.aiohttp import (
        ConfigurationBotFrameworkAuthentication,
        CloudAdapter,
    )

    class _BotConfig:
        APP_ID = CONFIG.app_id
        APP_PASSWORD = CONFIG.app_password
        APP_TYPE = "SingleTenant"
        APP_TENANTID = CONFIG.tenant_id

    _adapter = CloudAdapter(ConfigurationBotFrameworkAuthentication(_BotConfig()))
    _USE_CLOUD_ADAPTER = True
    logger.info("Usando CloudAdapter (Single Tenant, tenant=%s)", CONFIG.tenant_id)

except ImportError:
    # Fallback para versiones SDK < 4.14 — forzamos el tenant manualmente
    from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
    from botbuilder.schema import Activity as _Activity

    _settings = BotFrameworkAdapterSettings(
        app_id=CONFIG.app_id,
        app_password=CONFIG.app_password,
        channel_auth_tenant=CONFIG.tenant_id,
    )
    _adapter = BotFrameworkAdapter(_settings)
    # Forzar tenant en credenciales de salida (workaround SDK < 4.14)
    if CONFIG.tenant_id and hasattr(_adapter, "_credentials"):
        _adapter._credentials.tenant = CONFIG.tenant_id
    _USE_CLOUD_ADAPTER = False
    logger.warning("CloudAdapter no disponible — usando BotFrameworkAdapter con patch de tenant")

_bot = DiagnostiCoreBot()


async def _on_error(context, error: Exception) -> None:
    logger.exception("Bot error: %s", error)
    try:
        await context.send_activity("Lo siento, ocurrió un error interno. Intenta de nuevo.")
    except Exception:
        pass  # No propagar errores del handler de errores


if _USE_CLOUD_ADAPTER:
    _adapter.on_turn_error = _on_error
else:
    _adapter.on_turn_error = _on_error


# ── Endpoints ──────────────────────────────────────────────────────────────

async def messages(req: Request) -> Response:
    """
    POST /api/messages
    Azure Bot Service envía todas las actividades (mensajes, events,
    card submits, etc.) a este endpoint como JSON firmado.
    """
    if "application/json" not in req.content_type:
        return Response(status=415, text="Content-Type must be application/json")

    if _USE_CLOUD_ADAPTER:
        # CloudAdapter procesa la request aiohttp directamente
        response = Response()
        await _adapter.process(req, response, _bot.on_turn)
        return response
    else:
        # Fallback: deserializar manualmente
        from botbuilder.schema import Activity
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
    return json_response({
        "status": "ok",
        "app_id": CONFIG.app_id,
        "adapter": "CloudAdapter" if _USE_CLOUD_ADAPTER else "BotFrameworkAdapter",
        "tenant": CONFIG.tenant_id,
    })


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
        "DiagnostiCore Teams Bot arrancando en puerto %d | App ID: %s | Tenant: %s",
        CONFIG.port,
        CONFIG.app_id,
        CONFIG.tenant_id,
    )
    web.run_app(create_app(), host="0.0.0.0", port=CONFIG.port)
