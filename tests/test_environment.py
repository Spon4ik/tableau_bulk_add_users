import os

import pytest

from helpers import environment


def clear(monkeypatch):
    for name in [
        environment.SERVER,
        environment.SITE,
        environment.VERIFY_SSL,
        environment.AUTH_MODE,
        environment.PAT_NAME,
        environment.PAT_SECRET,
        environment.USERNAME,
        environment.PASSWORD,
        environment.LEGACY_USERNAME,
        environment.LEGACY_PASSWORD,
    ]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(environment, "refresh_process_from_user_environment", lambda names: None)
    monkeypatch.setattr(environment, "_broadcast_environment_change", lambda: None)


def test_noninteractive_requires_environment(monkeypatch):
    clear(monkeypatch)
    with pytest.raises(ValueError, match="Missing required Tableau environment"):
        environment.ensure_environment(interactive=False)


def test_interactive_pat_is_persisted_without_echoing_secret(monkeypatch):
    clear(monkeypatch)
    saved = {}
    monkeypatch.setattr(environment, "persist_user_environment", lambda name, value: (saved.__setitem__(name, value), os.environ.__setitem__(name, value)))
    answers = iter(["https://tableau.example.com", "", "", "my-pat"])

    env = environment.ensure_environment(
        interactive=True,
        prompt=lambda _: next(answers),
        secret_prompt=lambda _: "top-secret",
    )

    assert env.auth_mode == "pat"
    assert saved[environment.PAT_SECRET] == "top-secret"
    assert saved[environment.SITE] == ""
    assert saved[environment.VERIFY_SSL] == "true"


def test_password_auth_accepts_legacy_environment_names(monkeypatch):
    clear(monkeypatch)
    monkeypatch.setenv(environment.SERVER, "https://tableau.example.com")
    monkeypatch.setenv(environment.AUTH_MODE, "password")
    monkeypatch.setenv(environment.LEGACY_USERNAME, "legacy-admin")
    monkeypatch.setenv(environment.LEGACY_PASSWORD, "legacy-secret")

    env = environment.ensure_environment(interactive=False)

    assert env.auth_mode == "password"
    assert env.username == "legacy-admin"
    assert env.password == "legacy-secret"


def test_canonical_admin_credentials_take_precedence_over_legacy_names(monkeypatch):
    clear(monkeypatch)
    monkeypatch.setenv(environment.SERVER, "https://tableau.example.com")
    monkeypatch.setenv(environment.AUTH_MODE, "password")
    monkeypatch.setenv(environment.USERNAME, "current-admin")
    monkeypatch.setenv(environment.PASSWORD, "current-secret")
    monkeypatch.setenv(environment.LEGACY_USERNAME, "legacy-admin")
    monkeypatch.setenv(environment.LEGACY_PASSWORD, "legacy-secret")

    env = environment.ensure_environment(interactive=False)

    assert env.username == "current-admin"
    assert env.password == "current-secret"
