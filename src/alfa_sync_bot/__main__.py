import argparse
import json
from pathlib import Path
import sys
import time

from .shadow import run_shadow_import


def _shadow_parser(subparsers: argparse._SubParsersAction) -> None:
    shadow = subparsers.add_parser("shadow")
    shadow.add_argument("--report", required=True, type=Path)
    shadow.add_argument("--database", required=True, type=Path)
    shadow.add_argument(
        "--interval-seconds",
        default=0,
        type=int,
        help="Repeat the import at this interval; zero runs once.",
    )


def _print_shadow_result(result) -> None:
    print(
        json.dumps(
            {
                "changes": result.change_counts,
                "complete_sources": len(result.complete_sources),
                "rejected_lessons": result.rejected_lesson_count,
            },
            sort_keys=True,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alfa-sync-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _shadow_parser(subparsers)
    args = parser.parse_args(argv)

    if args.command != "shadow":
        parser.error("unknown command")
    if args.interval_seconds < 0:
        parser.error("--interval-seconds must not be negative")

    while True:
        try:
            result = run_shadow_import(args.report, args.database)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(f"shadow import failed: {error}", file=sys.stderr)
            return 2
        _print_shadow_result(result)
        if args.interval_seconds == 0:
            return 0
        try:
            time.sleep(args.interval_seconds)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
