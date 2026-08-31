#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from helpers.environment import ensure_environment
from helpers.logging_setup import configure_logging
from helpers.orchestrator import BulkAddOrchestrator
from helpers.tableau_service import TableauGroupService
from helpers.user_input import resolve_and_read_users, resolve_group_name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add existing Tableau site users to an existing local group."
    )
    parser.add_argument("--group", help="Exact existing local group name")
    parser.add_argument(
        "--users-file",
        type=Path,
        help=(
            "TXT/CSV users file. If omitted, interactive mode prompts for a path; "
            "otherwise project-root users.csv/users.txt is used as fallback."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and show intended changes")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for missing run inputs and environment configuration",
    )
    parser.add_argument(
        "--interactive-auth",
        action="store_true",
        help="Prompt only for missing environment configuration",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        group_name = resolve_group_name(args.group, interactive=args.interactive)
        users_file, users = resolve_and_read_users(
            args.users_file,
            interactive=args.interactive,
        )

        log_file = configure_logging(verbose=args.verbose)
        print(f"Users file: {users_file}")
        print(f"Requested users: {', '.join(users)}")
        print(f"Log file: {log_file}")

        env = ensure_environment(interactive=args.interactive or args.interactive_auth)
        service = TableauGroupService(env)
        report = BulkAddOrchestrator(service).run(
            group_name=group_name,
            users=users,
            dry_run=args.dry_run,
        )
        return 0 if report.ok else 1
    except (ValueError, LookupError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
