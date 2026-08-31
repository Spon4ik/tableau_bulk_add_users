# %%
#!/usr/bin/env python3
"""Add existing Tableau site users to an existing local group.

Sensitive connection and authentication values are read only from environment
variables. Usernames and the target group are supplied at runtime.

Required environment variables:
  TABLEAU_SERVER_URL
  TABLEAU_PAT_NAME and TABLEAU_PAT_SECRET
    OR TABLEAU_USERNAME and TABLEAU_PASSWORD

Optional environment variables:
  TABLEAU_SITE_CONTENT_URL   Default: "" (Default site)
  TABLEAU_VERIFY_SSL         Default: true

Examples:
  python tableau_bulk_add_users.py --group "Target Group" --users "user1,user2"
  python tableau_bulk_add_users.py --group "Target Group" --users-file users.txt
  python tableau_bulk_add_users.py --group "Target Group" --users-file users.csv --dry-run

The input file may be:
  * TXT: one username per line, or comma-separated values
  * CSV: a column named username, user, login, or name

This script does not create users or groups. It only adds existing site users
into an existing group. It deliberately avoids printing credentials, server
URLs, site names, group names, or usernames.
"""
# %%
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

try:
    import tableauserverclient as TSC
except ImportError:
    print(
        "Missing dependency: tableauserverclient. Install it with: "
        "python -m pip install tableauserverclient",
        file=sys.stderr,
    )
    raise SystemExit(2)
# %%
LOG = logging.getLogger("tableau_bulk_add_users")
CSV_COLUMNS = ("username", "user", "login", "name")


def env_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def normalize_users(values: Iterable[str]) -> list[str]:
    """Trim, remove blanks, and de-duplicate without changing order."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        username = value.strip()
        key = username.casefold()
        if username and key not in seen:
            result.append(username)
            seen.add(key)
    return result


def read_users_file(path: Path) -> list[str]:
    if not path.is_file():
        raise ValueError("Users file does not exist or is not a regular file")

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return []
            field_map = {field.strip().casefold(): field for field in reader.fieldnames}
            selected = next((field_map[c] for c in CSV_COLUMNS if c in field_map), None)
            if selected is None:
                if len(reader.fieldnames) == 1:
                    selected = reader.fieldnames[0]
                else:
                    raise ValueError(
                        "CSV must contain a username, user, login, or name column"
                    )
            return normalize_users(row.get(selected, "") for row in reader)

    text = path.read_text(encoding="utf-8-sig")
    return normalize_users(part for line in text.splitlines() for part in line.split(","))


def collect_users(args: argparse.Namespace) -> list[str]:
    values: list[str] = []
    if args.users:
        values.extend(args.users.split(","))
    if args.user:
        values.extend(args.user)
    if args.users_file:
        values.extend(read_users_file(args.users_file))
    return normalize_users(values)


def build_auth() -> object:
    site = os.getenv("TABLEAU_SITE_CONTENT_URL", "").strip()
    pat_name = os.getenv("TABLEAU_PAT_NAME", "").strip()
    pat_secret = os.getenv("TABLEAU_PAT_SECRET", "").strip()
    username = os.getenv("TABLEAU_USERNAME", "").strip()
    password = os.getenv("TABLEAU_PASSWORD", "").strip()

    if pat_name or pat_secret:
        if not (pat_name and pat_secret):
            raise ValueError("Both TABLEAU_PAT_NAME and TABLEAU_PAT_SECRET are required")
        return TSC.PersonalAccessTokenAuth(pat_name, pat_secret, site_id=site)

    if username or password:
        if not (username and password):
            raise ValueError("Both TABLEAU_USERNAME and TABLEAU_PASSWORD are required")
        return TSC.TableauAuth(username, password, site_id=site)

    raise ValueError(
        "Set either TABLEAU_PAT_NAME/TABLEAU_PAT_SECRET or "
        "TABLEAU_USERNAME/TABLEAU_PASSWORD"
    )


def exact_group(server: TSC.Server, group_name: str):
    matches = [g for g in TSC.Pager(server.groups) if g.name.casefold() == group_name.casefold()]
    if not matches:
        raise LookupError("Target group was not found on the selected Tableau site")
    if len(matches) > 1:
        raise LookupError("Multiple exact group matches were returned; no changes were made")
    return matches[0]


def site_users_by_name(server: TSC.Server) -> dict[str, object]:
    users: dict[str, object] = {}
    duplicates: set[str] = set()
    for item in TSC.Pager(server.users):
        key = item.name.casefold()
        if key in users:
            duplicates.add(key)
        else:
            users[key] = item
    for key in duplicates:
        users.pop(key, None)
    return users


def current_member_ids(server: TSC.Server, group) -> set[str]:
    server.groups.populate_users(group)
    return {user.id for user in (group.users or [])}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add existing Tableau site users to an existing local group."
    )
    parser.add_argument("--group", required=True, help="Exact target group name")
    parser.add_argument("--users", help="Comma-separated usernames")
    parser.add_argument(
        "--user", action="append", help="One username; repeat this option as needed"
    )
    parser.add_argument(
        "--users-file", type=Path, help="TXT or CSV file containing usernames"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and report without changes"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable operational debug messages"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        users = collect_users(args)
        if not users:
            raise ValueError("No users were supplied")

        server_url = env_required("TABLEAU_SERVER_URL")
        verify_ssl = env_bool("TABLEAU_VERIFY_SSL", True)
        auth = build_auth()

        server = TSC.Server(server_url, use_server_version=True)
        server.add_http_options({"verify": verify_ssl})
        if not verify_ssl:
            LOG.warning("TLS certificate verification is disabled")

        added = 0
        already_member = 0
        failed = 0
        not_found = 0

        with server.auth.sign_in(auth):
            group = exact_group(server, args.group)
            users_by_name = site_users_by_name(server)
            member_ids = current_member_ids(server, group)

            LOG.info("Validated target group and %d unique requested user(s)", len(users))

            for position, requested_name in enumerate(users, start=1):
                user = users_by_name.get(requested_name.casefold())
                safe_ref = f"user #{position}"

                if user is None:
                    not_found += 1
                    LOG.error("%s was not found uniquely on the selected site", safe_ref)
                    continue

                if user.id in member_ids:
                    already_member += 1
                    LOG.info("%s is already a group member", safe_ref)
                    continue

                if args.dry_run:
                    added += 1
                    LOG.info("%s would be added", safe_ref)
                    continue

                try:
                    server.groups.add_user(group, user.id)
                    member_ids.add(user.id)
                    added += 1
                    LOG.info("%s was added", safe_ref)
                except Exception as exc:
                    failed += 1
                    LOG.error("Could not add %s: %s", safe_ref, type(exc).__name__)

        action = "would_add" if args.dry_run else "added"
        LOG.info(
            "Summary: requested=%d, %s=%d, already_member=%d, not_found=%d, failed=%d",
            len(users), action, added, already_member, not_found, failed,
        )
        return 1 if failed or not_found else 0

    except (ValueError, LookupError) as exc:
        LOG.error("%s", exc)
        return 2
    except Exception as exc:
        LOG.error("Operation failed: %s", type(exc).__name__)
        if args.verbose:
            LOG.debug("Exception details", exc_info=True)
        return 1
# %%

if __name__ == "__main__":
    raise SystemExit(main())
