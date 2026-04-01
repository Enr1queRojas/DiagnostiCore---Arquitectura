"""
api — DiagnostiCore REST API and SSE streaming layer.

Exposes the diagnostic pipeline over HTTP via FastAPI:
  POST /api/runs                     — create run, get JWT token
  GET  /api/runs/{run_id}            — run status
  POST /api/runs/{run_id}/pipeline   — start pipeline (background task)
  GET  /api/runs/{run_id}/stream     — SSE real-time progress
  GET  /api/runs/{run_id}/report     — final markdown report

Run with:
  uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
"""

from api.app import app

__all__ = ["app"]
