from pathlib import Path

import pytest

from helpers.user_input import (
    normalize_users,
    read_users_file,
    resolve_group_name,
    resolve_users_file,
)


def test_normalize_users_preserves_order_and_deduplicates_case_insensitively():
    assert normalize_users([" Alice ", "bob", "ALICE", "", " Bob "]) == ["Alice", "bob"]


def test_simple_csv_is_a_comma_separated_user_list(tmp_path: Path):
    path = tmp_path / "users.csv"
    path.write_text("alice,bob\ncarol,ALICE\n", encoding="utf-8")

    assert read_users_file(path) == ["alice", "bob", "carol"]


def test_headered_csv_remains_supported(tmp_path: Path):
    path = tmp_path / "users.csv"
    path.write_text("username,comment\nalice,a\nbob,b\n", encoding="utf-8")

    assert read_users_file(path) == ["alice", "bob"]


def test_explicit_users_file_has_highest_precedence(tmp_path: Path):
    fallback = tmp_path / "users.csv"
    explicit = tmp_path / "custom.txt"
    fallback.write_text("fallback", encoding="utf-8")
    explicit.write_text("explicit", encoding="utf-8")

    assert resolve_users_file(explicit, project_root=tmp_path) == explicit


def test_interactive_path_wins_over_project_root_fallback(tmp_path: Path):
    fallback = tmp_path / "users.csv"
    chosen = tmp_path / "chosen.txt"
    fallback.write_text("fallback", encoding="utf-8")
    chosen.write_text("chosen", encoding="utf-8")

    resolved = resolve_users_file(
        interactive=True,
        project_root=tmp_path,
        input_fn=lambda _: str(chosen),
    )

    assert resolved == chosen


def test_blank_interactive_path_uses_project_root_csv_first(tmp_path: Path):
    csv_path = tmp_path / "users.csv"
    txt_path = tmp_path / "users.txt"
    csv_path.write_text("csv-user", encoding="utf-8")
    txt_path.write_text("txt-user", encoding="utf-8")

    resolved = resolve_users_file(
        interactive=True,
        project_root=tmp_path,
        input_fn=lambda _: "",
    )

    assert resolved == csv_path


def test_noninteractive_fallback_uses_users_txt_when_csv_absent(tmp_path: Path):
    txt_path = tmp_path / "users.txt"
    txt_path.write_text("alice,bob", encoding="utf-8")

    assert resolve_users_file(project_root=tmp_path) == txt_path


def test_missing_explicit_file_does_not_silently_fallback(tmp_path: Path):
    (tmp_path / "users.csv").write_text("fallback", encoding="utf-8")

    with pytest.raises(ValueError, match="does not exist"):
        resolve_users_file(tmp_path / "missing.csv", project_root=tmp_path)


def test_group_name_is_parameter_or_interactive_prompt():
    assert resolve_group_name("  Team A  ") == "Team A"
    assert resolve_group_name(interactive=True, input_fn=lambda _: "Team B") == "Team B"

    with pytest.raises(ValueError, match="--group"):
        resolve_group_name()
