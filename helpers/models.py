from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class UserStatus(str, Enum):
    ADDED = "added"
    WOULD_ADD = "would_add"
    ALREADY_MEMBER = "already_member"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    FAILED = "failed"


@dataclass(frozen=True)
class UserResult:
    username: str
    status: UserStatus
    detail: str = ""


@dataclass
class RunReport:
    group_name: str
    dry_run: bool
    requested_users: list[str]
    results: list[UserResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(
            item.status not in {UserStatus.NOT_FOUND, UserStatus.AMBIGUOUS, UserStatus.FAILED}
            for item in self.results
        )

    def counts(self) -> dict[str, int]:
        result = {status.value: 0 for status in UserStatus}
        for item in self.results:
            result[item.status.value] += 1
        return result
