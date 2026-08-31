from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

CSV_COLUMNS = ("username", "user", "login", "name")


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
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Users file does not exist: {path}")

    if path.suffix.casefold() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return []
            field_map = {field.strip().casefold(): field for field in reader.fieldnames}
            selected = next((field_map[name] for name in CSV_COLUMNS if name in field_map), None)
            if selected is None:
                if len(reader.fieldnames) == 1:
                    selected = reader.fieldnames[0]
                else:
                    raise ValueError("CSV must contain username, user, login, or name column")
            return normalize_users(row.get(selected, "") for row in reader)

    text = path.read_text(encoding="utf-8-sig")
    return normalize_users(part for line in text.splitlines() for part in line.split(","))
