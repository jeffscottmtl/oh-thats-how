from __future__ import annotations

import argparse
import logging
import sys

from .config import ConfigError
from .pipeline import PipelineError, run_pipeline
from .security import redact
from .utils import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-podcast", description="The Signal podcast pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the full production pipeline")
    run.add_argument("--output-dir", default="./output", help="Output directory for artifacts")
    run.add_argument(
        "--allow-domain",
        action="append",
        default=[],
        help="Approve additional source domain(s). Repeat flag for multiple domains.",
    )
    run.add_argument(
        "--stories",
        type=int,
        default=None,
        help="Optional preferred story count hint (manual selection is always required and not constrained)",
    )
    run.add_argument("--episode-number", type=int, default=None, help="Episode number to render in cover/metadata")
    run.add_argument(
        "--episode-date",
        default=None,
        help="Episode date override in YYYY-MM-DD (used for artifact naming and cover date)",
    )
    run.add_argument(
        "--window-start",
        default=None,
        help="Optional date-window start in YYYY-MM-DD for story discovery filtering",
    )
    run.add_argument(
        "--window-end",
        default=None,
        help="Optional date-window end in YYYY-MM-DD for story discovery filtering",
    )
    run.add_argument("--skip-audio", action="store_true", help="Skip audio generation")
    run.add_argument(
        "--skip-verification",
        action="store_true",
        help="Skip URL-reachability check during story verification (useful for offline testing)",
    )
    run.add_argument(
        "--qwen-profile-manifest",
        default=None,
        help="Override Qwen profile manifest CSV path (defaults to QWEN_PROFILE_MANIFEST env)",
    )
    run.add_argument(
        "--qwen-model",
        default=None,
        help="Override Qwen model id/path (defaults to QWEN_TTS_MODEL env)",
    )
    run.add_argument(
        "--qwen-ref-clip-id",
        default=None,
        help="Optional specific clip_id from profile_manifest.csv to force as Qwen reference",
    )
    run.add_argument(
        "--auto-confirm-audio",
        action="store_true",
        help="Skip confirmation prompt and generate audio automatically",
    )
    run.add_argument(
        "--env-file",
        default=None,
        help="Optional local env file path for development (vars are still read from env)",
    )
    run.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = getattr(logging, getattr(args, "log_level", "INFO"), logging.INFO)
    setup_logging(level=log_level)

    if args.command == "run":
        try:
            return run_pipeline(args)
        except (PipelineError, ConfigError, ValueError) as exc:
            logging.error("Pipeline error: %s", redact(str(exc)))
            return 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
