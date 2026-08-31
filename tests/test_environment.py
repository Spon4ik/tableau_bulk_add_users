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
