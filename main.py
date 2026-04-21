"""
main.py — DiagnostiCore Entry Point
=====================================
Triggers a full 360-degree diagnostic run from the command line.

Usage examples:
  # Create a brand-new run (interactive prompt for evidence)
  python main.py --cliente "Empresa ABC" --sector manufactura --consultor "Ana López"

  # Resume an existing run (skips already-completed agents)
  python main.py --run-id EMPRESAABC_20260330

  # Load evidence from a JSON file and run immediately
  python main.py --cliente "Corp XYZ" --sector servicios \
                 --consultor "Pedro" --evidencia examples/CompoLat_ejemplo.json

  # Verbose debug logging
  python main.py --run-id EMPRESAABC_20260330 -v

Exit codes:
  0  Pipeline completed successfully
  1  Pipeline failed (see logs for details)
  2  Invalid arguments
  130 Interrupted by user (Ctrl-C)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Project root on sys.path so that 'blackboard' and 'orchestrator' are importable
# when running: python main.py  (without installing the package)
_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from auth.jwt_auth import (
    TokenError,
    create_run_token,
    verify_run_token,
)
from blackboard.blackboard import Blackboard
from orchestrator import OrchestratorError, run_full_pipeline
from orchestrator.session_runner import SessionRunner
from orchestrator.managed_agent_setup import setup_managed_agents


# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────

def _setup_logging(verbose: bool) -> None:
    """Configures root logger with a human-friendly format."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s │ %(levelname)-8s │ %(name)-32s │ %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    # Quieten the noisy httpx logger used internally by the Anthropic SDK
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ─────────────────────────────────────────────────────────────────────────────
# Run initialisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _create_new_run(args: argparse.Namespace) -> str:
    """
    Creates a new diagnostic run from CLI arguments and optionally loads
    evidence from a JSON file.

    Returns:
        The run_id of the newly created run.
    """
    logger = logging.getLogger("main")

    bb = Blackboard.crear_run(
        nombre_cliente=args.cliente,
        sector=args.sector,
        consultor=args.consultor,
        tamaño=args.tamanio,
        empleados=args.empleados,
        runs_dir=args.runs_dir,
    )
    run_id: str = bb._data["run_id"]
    logger.info("New run created: %s", run_id)

    # Load evidence from a JSON file if provided
    if args.evidencia:
        _load_evidence_file(bb, Path(args.evidencia))

    # Generate a scoped JWT token for this run and print it to stdout.
    # The consultant must supply this token via --token to resume the run
    # in environments where multi-consultant isolation is enforced.
    token = create_run_token(
        run_id=run_id,
        consultor_id=args.consultor,
        ttl_hours=args.token_ttl,
    )
    print(f"\n  Run ID : {run_id}")
    print(f"  Token  : {token}")
    print(
        "  Keep this token — you will need it to resume the run with --token.\n"
    )

    return run_id


def _load_evidence_file(bb: Blackboard, evidence_path: Path) -> None:
    """
    Imports evidence from a JSON file into the active run.

    The file is expected to follow the structure of
    examples/CompoLat_ejemplo.json — specifically the 'evidencia' key.
    """
    logger = logging.getLogger("main")

    if not evidence_path.exists():
        logger.warning("Evidence file not found: %s — starting with empty evidence", evidence_path)
        return

    with open(evidence_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    # Support both top-level evidencia dict and a bare evidence container
    evidencia = raw.get("evidencia", raw)

    count = 0
    for t in evidencia.get("transcripciones", []):
        bb.add_evidencia_transcripcion(
            entrevistado_rol=t.get("entrevistado_rol", "Desconocido"),
            texto=t.get("texto", ""),
            dimension_primaria=t.get("dimension_primaria", ""),
        )
        count += 1

    logger.info("Loaded %d transcription(s) from: %s", count, evidence_path)


def _verify_existing_run(run_id: str, runs_dir: str) -> None:
    """Raises SystemExit if the specified run file does not exist."""
    run_path = Path(runs_dir) / f"{run_id}.json"
    if not run_path.exists():
        logging.getLogger("main").error(
            "Run file not found: %s\n"
            "Check the --run-id value and --runs-dir path.",
            run_path,
        )
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Main coroutine
# ─────────────────────────────────────────────────────────────────────────────

async def main(args: argparse.Namespace) -> int:
    logger = logging.getLogger("main")

    # ── Handle --setup flag (one-time setup, exits after completion) ──────────
    if args.setup:
        logger.info("Running one-time Managed Agent setup...")
        setup_managed_agents()
        logger.info("Setup complete. Config saved to config/managed_agents_config.json")
        print("\nSetup complete. Run IDs saved to config/managed_agents_config.json")
        print("You can now run diagnostics with: python main.py --cliente ...\n")
        return 0

    # ── Validate environment ──────────────────────────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        logger.error(
            "ANTHROPIC_API_KEY environment variable is not set.\n"
            "Export it before running: export ANTHROPIC_API_KEY=sk-ant-..."
        )
        return 1

    # ── Resolve run ───────────────────────────────────────────────────────────
    if args.run_id:
        run_id = args.run_id
        logger.info("Resuming existing run: %s", run_id)
        _verify_existing_run(run_id, args.runs_dir)

        # Token verification — optional but enforced when --token is supplied.
        # If DIAGNOSTICORE_JWT_SECRET is set, skipping --token logs a warning.
        if args.token:
            try:
                claims = verify_run_token(args.token, expected_run_id=run_id)
                logger.info(
                    "Token verified | run=%s | consultor=%s | expires=%s",
                    claims.run_id,
                    claims.consultor_id,
                    claims.expires_at.strftime("%Y-%m-%d %H:%M UTC"),
                )
            except TokenError as exc:
                logger.error("Token verification failed: %s", exc)
                return 1
        else:
            import os as _os
            if _os.environ.get("DIAGNOSTICORE_JWT_SECRET"):
                logger.warning(
                    "DIAGNOSTICORE_JWT_SECRET is set but --token was not provided. "
                    "Access is unauthenticated. Pass --token <token> to enforce isolation."
                )
    else:
        run_id = _create_new_run(args)

    # ── Initialise SessionRunner ──────────────────────────────────────────────
    runner = SessionRunner()
    logger.info("SessionRunner ready — Managed Agents mode")

    # ── Execute pipeline ──────────────────────────────────────────────────────
    logger.info("Starting DiagnostiCore pipeline | run=%s", run_id)

    try:
        results = await run_full_pipeline(
            run_id=run_id,
            runner=runner,
            runs_dir=args.runs_dir,
        )
    except OrchestratorError as exc:
        logger.error("Pipeline failed: %s", exc)
        if exc.failed_agents:
            logger.error("Failed agents: %s", exc.failed_agents)
        logger.error(
            "Run file preserved at: %s/%s.json — inspect it for partial results.",
            args.runs_dir, run_id,
        )
        return 1

    # ── Print summary ─────────────────────────────────────────────────────────
    bb_final = Blackboard(f"{args.runs_dir}/{run_id}.json")

    # Markdown run summary to stdout (the rest goes to stderr via logging)
    print("\n" + "═" * 60)
    print(bb_final.to_markdown_resumen())

    if "A7" in results:
        idd = results["A7"].get("idd", "N/A")
        n_causas = len(results["A7"].get("causas_raiz", []))
        print(f"\n  IDD final : {idd}/100")
        print(f"  Causas raíz identificadas : {n_causas}")

    if "A8" in results:
        print("\n  ✓ One-Pager generado y guardado en el blackboard.")

    print("═" * 60)
    print(f"\nRun guardado en: {args.runs_dir}/{run_id}.json\n")

    return 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI argument parser
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diagnosticore",
        description="DiagnostiCore — Sistema Agéntico de Diagnóstico 360",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Mutually exclusive: either resume an existing run, start a new one, or run setup
    run_source = parser.add_mutually_exclusive_group(required=True)
    run_source.add_argument(
        "--run-id",
        dest="run_id",
        metavar="RUN_ID",
        help="Resume an existing run by its ID (e.g. EMPRESAABC_20260330).",
    )
    run_source.add_argument(
        "--cliente",
        metavar="NOMBRE",
        help="Client name — starts a new diagnostic run.",
    )
    run_source.add_argument(
        "--setup",
        action="store_true",
        default=False,
        help=(
            "ONE-TIME: create Managed Agent objects and cloud environment. "
            "Run before the first diagnostic. Requires ANTHROPIC_API_KEY."
        ),
    )

    # New-run parameters (only meaningful when --cliente is used)
    parser.add_argument(
        "--sector",
        default="servicios",
        choices=[
            "manufactura", "inmobiliario", "comercializadora",
            "servicios", "tecnologia", "salud", "otro",
        ],
        help="Client industry sector (default: servicios).",
    )
    parser.add_argument(
        "--consultor",
        default="Consultor InnoVerse",
        metavar="NOMBRE",
        help="Name of the responsible consultant.",
    )
    parser.add_argument(
        "--tamanio",
        default="mediana",
        choices=["micro", "pequeña", "mediana", "grande"],
        help="Company size (default: mediana).",
    )
    parser.add_argument(
        "--empleados",
        type=int,
        default=0,
        metavar="N",
        help="Approximate headcount.",
    )
    parser.add_argument(
        "--evidencia",
        metavar="PATH",
        help=(
            "Path to a JSON evidence file to pre-load into the run. "
            "See examples/CompoLat_ejemplo.json for the expected format."
        ),
    )

    # Shared parameters
    parser.add_argument(
        "--runs-dir",
        dest="runs_dir",
        default="runs",
        metavar="DIR",
        help="Directory where run JSON files are stored (default: runs/).",
    )
    parser.add_argument(
        "--agents-dir",
        dest="agents_dir",
        default=None,
        metavar="DIR",
        help="Override the /agents/ directory location.",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        metavar="MODEL_ID",
        help="Anthropic model ID to use (default: claude-sonnet-4-6).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )

    # JWT auth (Fase 3)
    parser.add_argument(
        "--token",
        metavar="JWT",
        default=None,
        help=(
            "Bearer token to verify when resuming an existing run. "
            "Generated automatically when a new run is created. "
            "Required in multi-consultant environments where "
            "DIAGNOSTICORE_JWT_SECRET is set."
        ),
    )
    parser.add_argument(
        "--token-ttl",
        dest="token_ttl",
        type=int,
        default=8,
        metavar="HOURS",
        help="Lifetime in hours for the token generated on new run creation (default: 8).",
    )

    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _parser = _build_parser()
    _args = _parser.parse_args()
    _setup_logging(_args.verbose)

    try:
        _exit_code = asyncio.run(main(_args))
    except KeyboardInterrupt:
        logging.getLogger("main").info("Interrupted by user.")
        _exit_code = 130

    sys.exit(_exit_code)
