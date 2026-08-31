from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Iterable

CSV_COLUMNS = ("username", "user", "login", "name")
DEFAULT_USER_FILENAMES = ("users.csv", "users.txt")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def normalize_users(values: Iterable[str]) -> list[str]:
    """Trim, remove blanks, and de-duplicate case-insensitively in input order."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        username = value.strip()
        key = username.casefold()
        if username and key not in seen:
            seen.add(key)
            result.append(username)
    return result


def read_users_file(path: str | Path) -> list[str]:
    """Read usernames from a simple comma-separated TXT/CSV or a headered CSV."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Users file does not exist: {path}")

    if path.suffix.casefold() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = [
                row
                for row in csv.reader(handle)
                if any(cell.strip() for cell in row)
            ]
        if not rows:
            return []

        header = [cell.strip().casefold() for cell in rows[0]]
        selected_index = next(
            (header.index(name) for name in CSV_COLUMNS if name in header),
            None,
        )
        if selected_index is not None:
            return normalize_users(
                row[selected_index] if selected_index < len(row) else ""
                for row in rows[1:]
            )

        return normalize_users(cell for row in rows for cell in row)

    text = path.read_text(encoding="utf-8-sig")
    return normalize_users(
        part
        for line in text.splitlines()
        for part in line.split(",")
    )


def find_default_users_file(project_root: str | Path | None = None) -> Path | None:
    """Return project-root users.csv first, then users.txt, when present."""
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    for filename in DEFAULT_USER_FILENAMES:
        candidate = root / filename
        if candidate.is_file():
            return candidate
    return None


def resolve_users_file(
    explicit_path: str | Path | None = None,
    *,
    interactive: bool = False,
    project_root: str | Path | None = None,
    input_fn: Callable[[str], str] = input,
) -> Path:
    """Resolve users-file input: parameter, interactive prompt, then root fallback."""
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if not path.is_file():
            raise ValueError(f"Users file does not exist: {path}")
        return path

    fallback = find_default_users_file(project_root)

    if interactive:
        if fallback is not None:
            raw = input_fn(
                f"Users file path [Enter for {fallback}]: "
            ).strip()
        else:
            raw = input_fn("Users file path: ").strip()

        if raw:
            path = Path(raw).expanduser()
            if not path.is_file():
                raise ValueError(f"Users file does not exist: {path}")
            return path

    if fallback is not None:
        return fallback

    raise ValueError(
        "No users file was supplied and neither users.csv nor users.txt "
        "exists in the project root"
    )


def resolve_and_read_users(
    explicit_path: str | Path | None = None,
    *,
    interactive: bool = False,
    project_root: str | Path | None = None,
    input_fn: Callable[[str], str] = input,
) -> tuple[Path, list[str]]:
    path = resolve_users_file(
        explicit_path,
        interactive=interactive,
        project_root=project_root,
        input_fn=input_fn,
    )
    users = read_users_file(path)
    if not users:
        raise ValueError(f"No users were found in users file: {path}")
    return path, users


def resolve_group_name(
    group_name: str | None = None,
    *,
    interactive: bool = False,
    input_fn: Callable[[str], str] = input,
) -> str:
    resolved = (group_name or "").strip()
    if not resolved and interactive:
        resolved = input_fn("Existing local Tableau group name: ").strip()
    if not resolved:
        raise ValueError("--group is required for non-interactive runs")
    return resolved
