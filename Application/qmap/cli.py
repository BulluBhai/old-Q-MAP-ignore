"""Minimal command-line entry point: ingest, preview, recover, verify.

This is deliberately not a front end. The analytical engine stays independent of any interface;
a web, Excel or desktop front end can call the same functions later.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .core.config import load_settings
from .core.errors import QmapError
from .core.logging_setup import configure_console
from .core.runs import run_context
from .data_engine.ingest import ingest_file
from .data_engine.preview import preview_file
from .data_engine.profiles import check_profile_against_settings, find_profile
from .storage.db import open_database
from .storage.recovery import recover_incomplete, verify_registry


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m qmap", description="Q-MAP foundation tools (Stage 2).")
    p.add_argument("--version", action="version", version=f"qmap {__version__}")
    p.add_argument("--config", help="path of your local configuration file (or set QMAP_CONFIG)")
    sub = p.add_subparsers(dest="command", required=True)

    ing = sub.add_parser("ingest", help="ingest one or more files with a source profile")
    ing.add_argument("--profile", required=True, help="profile name (in Configuration/source_profiles) or a .toml path")
    ing.add_argument("--source-label", help="where the file came from (recorded with the receipt)")
    ing.add_argument("--note", help="free-text note recorded with the receipt")
    ing.add_argument("--exchange", help="exchange, when the profile takes it from the ingest request")
    ing.add_argument("--symbol", help="symbol, when the profile takes it from the ingest request")
    ing.add_argument("--timeframe", help="timeframe, when the profile takes it from the ingest request")
    ing.add_argument("--force-reason", help="written reason to retry a previously rejected file unchanged")
    ing.add_argument("files", nargs="+")

    pre = sub.add_parser("preview", help="inspect a file without registering anything")
    pre.add_argument("--profile", help="optional profile to test against the file")
    pre.add_argument("--exchange")
    pre.add_argument("--symbol")
    pre.add_argument("--timeframe")
    pre.add_argument("file")

    sub.add_parser("recover", help="finish or clean up interrupted work and report problems")
    sub.add_parser("verify", help="re-check every registered file against its checksum")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        settings = load_settings(args.config)
        configure_console(settings.log_level)
        if args.command == "preview":
            profile = find_profile(settings, args.profile) if args.profile else None
            if profile:
                check_profile_against_settings(profile, settings)
            print(preview_file(args.file, profile, settings, exchange=args.exchange, symbol=args.symbol,
                               timeframe=args.timeframe))
            return 0
        db = open_database(settings.db_path)
        if args.command in ("recover", "verify"):
            report = (recover_incomplete if args.command == "recover" else verify_registry)(settings, db)
            summary = report.summary()
            if summary == "nothing to recover":
                summary = "no problems found" if args.command == "recover" else "no problems found; every registered file matches its checksum"
            print(f"{args.command}: {summary}")
            for label in ("orphan_raw_files", "missing_files", "checksum_mismatches"):
                for item in getattr(report, label):
                    print(f"  {label}: {item}")
            return 1 if report.needs_attention else 0
        profile = find_profile(settings, args.profile)
        exit_code = 0
        with run_context(settings, db, "FOUND", area="Ingestion", module_name="Foundation",
                         params={"command": "ingest", "profile": profile.profile_id,
                                 "files": [str(f) for f in args.files]}) as run:
            for f in args.files:
                res = ingest_file(run, f, profile, source_label=args.source_label, note=args.note,
                                  force_reason=args.force_reason, exchange=args.exchange, symbol=args.symbol,
                                  timeframe=args.timeframe)
                print(f"{res.outcome.upper():11s} {f}\n            {res.message}")
                if res.issues_report:
                    print(f"            issues report: {res.issues_report}")
                if not res.ok:
                    exit_code = 1
            print(f"Run {run.run_id}  outputs: {run.dir}")
        return exit_code
    except QmapError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
