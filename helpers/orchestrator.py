from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from .models import RunReport, UserResult, UserStatus
from .user_input import normalize_users

LOG = logging.getLogger("tableau_bulk_add_users")
Reporter = Callable[[str], None]


def _default_reporter(message: str) -> None:
    print(message, flush=True)
    LOG.info(message)


class BulkAddOrchestrator:
    """Interactive-friendly workflow over an injected Tableau service."""

    def __init__(self, service, reporter: Reporter = _default_reporter):
        self.service = service
        self.report = reporter

    def run(self, *, group_name: str, users: Iterable[str], dry_run: bool = False) -> RunReport:
        requested = normalize_users(users)
        if not requested:
            raise ValueError("No users were supplied")
        if not group_name.strip():
            raise ValueError("Group name cannot be empty")

        report = RunReport(group_name=group_name, dry_run=dry_run, requested_users=requested)

        self.report("[1/5] Authenticating to Tableau...")
        with self.service.signed_in():
            auth = self.service.auth_status()
            self.report(f"      Authentication: OK (REST API {auth.server_version})")

            self.report(f"[2/5] Requested users ({len(requested)}):")
            for username in requested:
                self.report(f"      - {username}")

            self.report(f"[3/5] Resolving existing local group: {group_name}")
            group = self.service.get_exact_local_group(group_name)
            self.report("      Group: OK (existing local group)")

            self.report("[4/5] Resolving site users and current group membership...")
            users_by_name, duplicate_names = self.service.users_by_casefolded_name()
            member_ids = self.service.group_member_ids(group)
            self.report(f"      Current group members: {len(member_ids)}")

            self.report("[5/5] Applying membership changes...")
            for username in requested:
                key = username.casefold()
                if key in duplicate_names:
                    result = UserResult(username, UserStatus.AMBIGUOUS, "multiple site users matched")
                    report.results.append(result)
                    self.report(f"      {username}: AMBIGUOUS — multiple site users matched")
                    continue

                user = users_by_name.get(key)
                if user is None:
                    result = UserResult(username, UserStatus.NOT_FOUND, "user not found on site")
                    report.results.append(result)
                    self.report(f"      {username}: NOT FOUND")
                    continue

                if user.id in member_ids:
                    result = UserResult(username, UserStatus.ALREADY_MEMBER)
                    report.results.append(result)
                    self.report(f"      {username}: ALREADY MEMBER")
                    continue

                if dry_run:
                    result = UserResult(username, UserStatus.WOULD_ADD)
                    report.results.append(result)
                    self.report(f"      {username}: WOULD ADD")
                    continue

                self.report(f"      {username}: attempting add...")
                try:
                    changed = self.service.add_user_to_group(group, user)
                    member_ids.add(user.id)
                    if changed is False:
                        result = UserResult(username, UserStatus.ALREADY_MEMBER, "membership changed during run")
                        report.results.append(result)
                        self.report(f"      {username}: ALREADY MEMBER (race-safe conflict)")
                    else:
                        result = UserResult(username, UserStatus.ADDED)
                        report.results.append(result)
                        self.report(f"      {username}: ADDED")
                except Exception as exc:
                    LOG.exception("Failed to add user %s", username)
                    result = UserResult(username, UserStatus.FAILED, type(exc).__name__)
                    report.results.append(result)
                    self.report(f"      {username}: FAILED ({type(exc).__name__})")

        counts = report.counts()
        self.report(
            "Summary: "
            + ", ".join(f"{name}={count}" for name, count in counts.items() if count)
        )
        return report
