from contextlib import contextmanager
from types import SimpleNamespace

from helpers.models import UserStatus
from helpers.orchestrator import BulkAddOrchestrator


class FakeService:
    def __init__(self):
        self.group = SimpleNamespace(name="Local Group", domain_name="local", id="g1")
        self.users = {
            "alice": SimpleNamespace(name="alice", id="u1"),
            "bob": SimpleNamespace(name="bob", id="u2"),
        }
        self.members = {"u1"}
        self.added = []

    @contextmanager
    def signed_in(self):
        yield self

    def auth_status(self):
        return SimpleNamespace(authenticated=True, server_version="3.29")

    def get_exact_local_group(self, name):
        assert name == "Local Group"
        return self.group

    def users_by_casefolded_name(self):
        return self.users, set()

    def group_member_ids(self, group):
        return set(self.members)

    def add_user_to_group(self, group, user):
        self.added.append(user.id)


def test_orchestrator_is_idempotent_and_reports_per_user_status():
    service = FakeService()
    lines = []
    report = BulkAddOrchestrator(service, reporter=lines.append).run(
        group_name="Local Group",
        users=["alice", "bob", "missing", "BOB"],
    )

    assert [item.status for item in report.results] == [
        UserStatus.ALREADY_MEMBER,
        UserStatus.ADDED,
        UserStatus.NOT_FOUND,
    ]
    assert service.added == ["u2"]
    assert any("Authentication: OK" in line for line in lines)
    assert any("bob: attempting add" in line for line in lines)


def test_dry_run_does_not_mutate():
    service = FakeService()
    report = BulkAddOrchestrator(service, reporter=lambda _: None).run(
        group_name="Local Group",
        users=["bob"],
        dry_run=True,
    )
    assert report.results[0].status is UserStatus.WOULD_ADD
    assert service.added == []
