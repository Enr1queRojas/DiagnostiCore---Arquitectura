"""
teams_bot/bot.py
=================
ActivityHandler principal del bot de DiagnostiCore.

Flujo de comandos:
  nuevo              → muestra formulario de nuevo run
  estado [run_id]    → muestra progreso del pipeline
  reporte [run_id]   → muestra reporte final
  ayuda / help / ?   → welcome card

El estado de run_id y token por conversación se guarda en
_conversation_state (en memoria). En producción multi-instancia
reemplazar con Azure Cosmos DB state store.
"""
from __future__ import annotations

import logging
from typing import Any

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import Activity, ActivityTypes, Attachment

from teams_bot import adaptive_cards as cards
from teams_bot.config import CONFIG
from teams_bot.diagnosticore_client import DiagnostiCoreClient

logger = logging.getLogger(__name__)

# Estado en memoria: conversation_id → {run_id, token}
_conversation_state: dict[str, dict[str, str]] = {}


def _attachment(card: dict) -> Attachment:
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card,
    )


def _conversation_id(turn_context: TurnContext) -> str:
    return turn_context.activity.conversation.id


class DiagnostiCoreBot(ActivityHandler):
    def __init__(self) -> None:
        self._client = DiagnostiCoreClient(CONFIG.diagnosticore_api_url)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def on_members_added_activity(
        self,
        members_added: list,
        turn_context: TurnContext,
    ) -> None:
        """Bienvenida al instalar el bot en un canal o chat."""
        bot_id = turn_context.activity.recipient.id
        for member in members_added:
            if member.id != bot_id:
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        attachments=[_attachment(cards.welcome_card())],
                    )
                )

    # ── Entry point ───────────────────────────────────────────────────────

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        # Adaptive Card submit → activity.value es un dict
        if turn_context.activity.value:
            await self._handle_card_action(turn_context, turn_context.activity.value)
            return

        text: str = (turn_context.activity.text or "").strip()
        # En canales Teams el bot recibe "<at>BotName</at> comando" — strip mention
        if "<at>" in text:
            import re
            text = re.sub(r"<at>[^<]+</at>", "", text).strip()

        cmd, _, args = text.lower().partition(" ")
        args = args.strip()

        if cmd in ("nuevo", "new", "iniciar"):
            await self._cmd_nuevo(turn_context)
        elif cmd in ("estado", "status"):
            await self._cmd_estado(turn_context, args)
        elif cmd in ("reporte", "report", "resultado"):
            await self._cmd_reporte(turn_context, args)
        else:
            await self._cmd_ayuda(turn_context)

    # ── Comandos de texto ─────────────────────────────────────────────────

    async def _cmd_nuevo(self, ctx: TurnContext) -> None:
        await ctx.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[_attachment(cards.new_run_form_card())],
            )
        )

    async def _cmd_estado(self, ctx: TurnContext, run_id_arg: str) -> None:
        run_id, token = self._resolve_run(ctx, run_id_arg)
        if not run_id:
            await ctx.send_activity(
                "Indica el Run ID: `estado EMPRESA_20260426`  \n"
                "O inicia uno nuevo con `nuevo`."
            )
            return
        await self._send_status(ctx, run_id, token)

    async def _cmd_reporte(self, ctx: TurnContext, run_id_arg: str) -> None:
        run_id, token = self._resolve_run(ctx, run_id_arg)
        if not run_id:
            await ctx.send_activity(
                "Indica el Run ID: `reporte EMPRESA_20260426`"
            )
            return
        await self._send_report(ctx, run_id, token)

    async def _cmd_ayuda(self, ctx: TurnContext) -> None:
        await ctx.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[_attachment(cards.welcome_card())],
            )
        )

    # ── Acciones de Adaptive Cards ────────────────────────────────────────

    async def _handle_card_action(self, ctx: TurnContext, value: dict[str, Any]) -> None:
        action = value.get("action", "")

        if action == "show_new_run_form":
            await self._cmd_nuevo(ctx)

        elif action == "create_run":
            await self._action_create_run(ctx, value)

        elif action == "start_pipeline":
            await self._action_start_pipeline(ctx, value.get("run_id", ""))

        elif action in ("refresh_status", "get_status"):
            run_id = value.get("run_id", "")
            _, token = self._resolve_run(ctx, run_id)
            await self._send_status(ctx, run_id, token)

        elif action == "get_report":
            run_id = value.get("run_id", "")
            _, token = self._resolve_run(ctx, run_id)
            await self._send_report(ctx, run_id, token)

        elif action == "cancel":
            await ctx.send_activity("Operación cancelada.")

        else:
            logger.warning("Acción desconocida en card: %s", action)

    async def _action_create_run(self, ctx: TurnContext, form: dict) -> None:
        cliente = form.get("cliente", "").strip()
        sector = form.get("sector", "otro")
        tamanio = form.get("tamanio", "mediana")
        consultor = form.get("consultor", "").strip()
        try:
            empleados = int(form.get("empleados", 0))
        except (TypeError, ValueError):
            empleados = 0

        if not cliente or not consultor:
            await ctx.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[_attachment(cards.error_card("Nombre del cliente y consultor son obligatorios."))],
                )
            )
            return

        await ctx.send_activity("⏳ Creando el run…")
        try:
            result = await self._client.create_run(
                cliente=cliente,
                sector=sector,
                consultor=consultor,
                tamanio=tamanio,
                empleados=empleados,
            )
        except Exception as exc:
            logger.exception("create_run error")
            await ctx.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[_attachment(cards.error_card(f"No se pudo crear el run: {exc}"))],
                )
            )
            return

        run_id: str = result["run_id"]
        token: str = result["token"]
        _conversation_state[_conversation_id(ctx)] = {"run_id": run_id, "token": token}

        await ctx.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[_attachment(cards.run_created_card(run_id, cliente))],
            )
        )

    async def _action_start_pipeline(self, ctx: TurnContext, run_id: str) -> None:
        conv_id = _conversation_id(ctx)
        state = _conversation_state.get(conv_id, {})
        token = state.get("token", "")

        if not token:
            await ctx.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[_attachment(cards.error_card(
                        "No hay token para este run en esta conversación. "
                        "Crea el run con `nuevo` primero."
                    ))],
                )
            )
            return

        await ctx.send_activity("⏳ Iniciando pipeline…")
        try:
            await self._client.start_pipeline(run_id=run_id, token=token)
        except Exception as exc:
            logger.exception("start_pipeline error")
            await ctx.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[_attachment(cards.error_card(f"Error al iniciar pipeline: {exc}"))],
                )
            )
            return

        await ctx.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[_attachment(cards.pipeline_started_card(run_id))],
            )
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _resolve_run(self, ctx: TurnContext, run_id_arg: str) -> tuple[str, str]:
        """
        Devuelve (run_id, token). Prioriza run_id_arg si se pasa;
        sino usa el último run guardado en la conversación.
        Token solo está disponible si el run fue creado en esta conversación.
        """
        state = _conversation_state.get(_conversation_id(ctx), {})
        run_id = run_id_arg or state.get("run_id", "")
        token = state.get("token", "") if not run_id_arg else ""
        if run_id_arg and run_id_arg == state.get("run_id"):
            token = state.get("token", "")
        return run_id, token

    async def _send_status(self, ctx: TurnContext, run_id: str, token: str) -> None:
        try:
            status = await self._client.get_status(run_id=run_id, token=token)
        except Exception as exc:
            logger.exception("get_status error")
            await ctx.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[_attachment(cards.error_card(f"No se pudo obtener el estado: {exc}"))],
                )
            )
            return
        await ctx.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[_attachment(cards.run_status_card(status))],
            )
        )

    async def _send_report(self, ctx: TurnContext, run_id: str, token: str) -> None:
        try:
            report = await self._client.get_report(run_id=run_id, token=token)
        except Exception as exc:
            logger.exception("get_report error")
            msg = (
                f"El diagnóstico todavía está en curso. Usa `estado {run_id}` para ver el progreso."
                if "202" in str(exc)
                else f"No se pudo obtener el reporte: {exc}"
            )
            await ctx.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[_attachment(cards.error_card(msg))],
                )
            )
            return
        await ctx.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[_attachment(cards.report_card(report, run_id))],
            )
        )
