#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from helpers.environment import ensure_environment
from helpers.logging_setup import configure_logging
from helpers.orchestrator import BulkAddOrchestrator
from helpers.tableau_service import TableauGroupService
from helpers.user_input import normalize_users, read_users_file


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add existing Tableau site users to an existing local group."
    )
    parser.add_argument("--group", help="Exact existing local group name")
    parser.add_argument("--users", help="Comma-separated Tableau usernames")
    parser.add_argument("--user", action="append", default=[], help="One username; repeatable")
    parser.add_argument("--users-file", type=Path, help="TXT or CSV containing usernames")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show intended changes")
    parser.add_argument("--interactive", action="store_true", help="Prompt for missing run inputs and environment configuration")
    parser.add_argument("--interactive-auth", action="store_true", help="Prompt only for missing environment configuration")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def collect_users(args: argparse.Namespace) -> list[str]:
    values: list[str] = []
    if args.users:
        values.extend(args.users.split(","))
    values.extend(args.user)
    if args.users_file:
        values.extend(read_users_file(args.users_file))
    return normalize_users(values)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        group_name = (args.group or "").strip()
        if not group_name and args.interactive:
            group_name = input("Existing local Tableau group name: ").strip()
        if not group_name:
            raise ValueError("--group is required unless --interactive is used")

        users = collect_users(args)
        if not users and args.interactive:
            raw = input("Tableau usernames (comma-separated): ")
            users = normalize_users(raw.split(","))
        if not users:
            raise ValueError("No users were supplied")

        log_file = configure_logging(verbose=args.verbose)
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
