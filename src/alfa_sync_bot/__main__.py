import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

from .database import apply_migrations
from .gemini_fallback import GeminiFallback
from .shadow import consume_import_request, run_shadow_import
from .telegram_api import TelegramApiError, TelegramHttpClient
from .telegram_runtime import process_updates


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


def _telegram_parser(subparsers: argparse._SubParsersAction) -> None:
    telegram = subparsers.add_parser("telegram")
    telegram.add_argument("--database", required=True, type=Path)


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


def _wait_for_shadow_trigger(database_path: Path, interval_seconds: int) -> None:
    deadline = time.monotonic() + interval_seconds
    while time.monotonic() < deadline:
        connection = sqlite3.connect(database_path)
        try:
            if consume_import_request(connection):
                return
        finally:
            connection.close()
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alfa-sync-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _shadow_parser(subparsers)
    _telegram_parser(subparsers)
    args = parser.parse_args(argv)

    if args.command == "telegram":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            print("TELEGRAM_BOT_TOKEN is required", file=sys.stderr)
            return 2
        connection = sqlite3.connect(args.database)
        try:
            apply_migrations(connection)
            client = TelegramHttpClient(token)
            gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
            gemini_model = os.environ.get(
                "GEMINI_MODEL", "gemini-3.1-flash-lite-preview"
            ).strip()
            fallback = (
                GeminiFallback(gemini_key, gemini_model) if gemini_key else None
            )
            while True:
                try:
                    process_updates(client, connection, fallback=fallback)
                except TelegramApiError as error:
                    print(f"telegram polling failed: {error}", file=sys.stderr)
                    time.sleep(5)
        except KeyboardInterrupt:
            return 0
        finally:
            connection.close()

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
            _wait_for_shadow_trigger(args.database, args.interval_seconds)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
