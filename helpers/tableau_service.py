from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import tableauserverclient as TSC
from tableauserverclient import ServerResponseError

from .environment import TableauEnvironment


@dataclass(frozen=True)
class AuthStatus:
    authenticated: bool
    server_version: str


class TableauGroupService:
    """Thin TSC adapter; orchestration logic intentionally lives elsewhere."""

    def __init__(self, env: TableauEnvironment):
        self.env = env
        self.server = TSC.Server(env.server_url, use_server_version=True)
        self.server.add_http_options({"verify": env.verify_ssl})

        if env.auth_mode == "pat":
            self.auth = TSC.PersonalAccessTokenAuth(
                env.pat_name,
                env.pat_secret,
                site_id=env.site_content_url,
            )
        else:
            self.auth = TSC.TableauAuth(
                env.username,
                env.password,
                site_id=env.site_content_url,
            )

    @contextmanager
    def signed_in(self) -> Iterator["TableauGroupService"]:
        with self.server.auth.sign_in(self.auth):
            yield self

    def auth_status(self) -> AuthStatus:
        version = str(getattr(self.server, "version", "unknown"))
        return AuthStatus(authenticated=True, server_version=version)

    def get_exact_local_group(self, group_name: str):
        matches = [
            group
            for group in TSC.Pager(self.server.groups)
            if (group.name or "").casefold() == group_name.casefold()
        ]
        if not matches:
            raise LookupError(f"Group not found: {group_name}")
        if len(matches) != 1:
            raise LookupError(f"Expected one exact group match, got {len(matches)}: {group_name}")

        group = matches[0]
        domain = (getattr(group, "domain_name", None) or "").casefold()
        # TSC can return None for local groups when Tableau omits the import/domain element.
        if domain and domain != "local":
            raise ValueError(f"Target group is not local (domain={group.domain_name!r})")
        return group

    def users_by_casefolded_name(self) -> tuple[dict[str, object], set[str]]:
        unique: dict[str, object] = {}
        duplicates: set[str] = set()
        for user in TSC.Pager(self.server.users):
            key = (user.name or "").casefold()
            if key in unique:
                duplicates.add(key)
            else:
                unique[key] = user
        for key in duplicates:
            unique.pop(key, None)
        return unique, duplicates

    def group_member_ids(self, group) -> set[str]:
        self.server.groups.populate_users(group)
        return {member.id for member in group.users}

    def add_user_to_group(self, group, user) -> bool:
        try:
            self.server.groups.add_user(group, user.id)
            return True
        except ServerResponseError as exc:
            if exc.code == "409011":
                # Race-safe idempotency: membership may have changed after preflight.
                return False
            raise
