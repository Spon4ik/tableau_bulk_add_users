from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = PROJECT_ROOT / "tableau_bulk_add_users.ipynb"


def _notebook() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _first_code_cell_source() -> str:
    for cell in _notebook()["cells"]:
        if cell.get("cell_type") == "code":
            return "".join(cell.get("source", []))
    raise AssertionError("Notebook has no code cells")


def test_notebook_is_committed_without_error_outputs():
    for cell in _notebook()["cells"]:
        for output in cell.get("outputs", []):
            assert output.get("output_type") != "error"


def test_notebook_import_cell_recovers_stale_user_input_module():
    import_cell = _first_code_cell_source()
    script = f"""
import helpers.user_input as user_input

# Reproduce the live-kernel failure: the module object is already cached from an
# older checkout and therefore does not yet expose the newly added helper.
if hasattr(user_input, "resolve_and_read_users"):
    del user_input.resolve_and_read_users
if hasattr(user_input, "resolve_group_name"):
    del user_input.resolve_group_name

namespace = {{}}
exec({import_cell!r}, namespace)

assert callable(namespace["resolve_and_read_users"])
assert callable(namespace["resolve_group_name"])
assert callable(namespace["ensure_environment"])
assert callable(namespace["configure_logging"])
assert namespace["TableauGroupService"] is not None
assert namespace["BulkAddOrchestrator"] is not None
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        check=True,
    )
