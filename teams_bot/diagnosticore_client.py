"""
teams_bot/diagnosticore_client.py
===================================
Cliente HTTP asíncrono para la API REST de DiagnostiCore (api/app.py).

Cada método corresponde a un endpoint. El token Bearer se obtiene al
crear el run y se pasa en todas las llamadas posteriores.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class DiagnostiCoreClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    # ── Runs ──────────────────────────────────────────────────────────────

    async def create_run(
        self,
        cliente: str,
        sector: str,
        consultor: str,
        tamanio: str,
        empleados: int,
    ) -> dict:
        """
        POST /api/runs
        Devuelve: {run_id, token, created_at, token_expires_at}
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.post(
                f"{self._base}/api/runs",
                json={
                    "cliente": cliente,
                    "sector": sector,
                    "consultor": consultor,
                    "tamanio": tamanio,
                    "empleados": empleados,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def start_pipeline(
        self,
        run_id: str,
        token: str,
        model: str = "claude-opus-4-7",
    ) -> dict:
        """
        POST /api/runs/{run_id}/pipeline
        Devuelve 202 inmediatamente. El progreso llega por SSE.
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.post(
                f"{self._base}/api/runs/{run_id}/pipeline",
                headers={"Authorization": f"Bearer {token}"},
                json={"model": model},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_status(self, run_id: str, token: str) -> dict:
        """GET /api/runs/{run_id}"""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.get(
                f"{self._base}/api/runs/{run_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_report(self, run_id: str, token: str) -> dict:
        """GET /api/runs/{run_id}/report"""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.get(
                f"{self._base}/api/runs/{run_id}/report",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def stream_events(
        self, run_id: str, token: str
    ) -> AsyncIterator[dict]:
        """
        GET /api/runs/{run_id}/stream
        Genera eventos SSE como dicts {type, data} hasta que el pipeline
        termina o el generador se abandona.
        """
        import json as _json

        url = f"{self._base}/api/runs/{run_id}/stream"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as http:
            async with http.stream("GET", url, headers=headers) as resp:
                resp.raise_for_status()
                event_type = "message"
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        raw = line[5:].strip()
                        try:
                            data = _json.loads(raw)
                        except _json.JSONDecodeError:
                            data = {"raw": raw}
                        yield {"type": event_type, "data": data}
                        if event_type in ("pipeline_done", "pipeline_error"):
                            return
                    elif line == "":
                        event_type = "message"
