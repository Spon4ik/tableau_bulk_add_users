# Tableau Bulk Add Users

Add **existing Tableau site users** to an **existing local Tableau group**, with the same reusable orchestration available from Jupyter and unattended Windows Task Scheduler runs.

## Design

The repository follows the patterns used by Tableau's official `tableauserverclient` (TSC) samples: TSC handles REST API version negotiation and pagination, membership is checked before mutation, and Tableau's `409011` "already in group" response is treated as an idempotent state rather than a fatal error.

The important architectural rule is that business logic lives under `helpers/`. The notebook and CLI are only front ends.

- `helpers/environment.py` — persistent Windows user-environment configuration and interactive credential bootstrap.
- `helpers/tableau_service.py` — thin TSC adapter.
- `helpers/orchestrator.py` — step-by-step workflow and per-user statuses.
- `helpers/user_input.py` — users-file resolution, TXT/CSV parsing, group prompting, and de-duplication.
- `tableau_bulk_add_users.py` — scheduler/CLI entry point.
- `tableau_bulk_add_users.ipynb` — interactive notebook using the same helpers.
- `Run.cmd` — Windows launcher with a project-local virtual environment.

## Authentication and environment variables

No credentials are accepted as command-line arguments and no `.env` file is used.

Required connection variables:

- `TABLEAU_SERVER_URL`
- `TABLEAU_SITE_CONTENT_URL` (blank means Default site)
- `TABLEAU_VERIFY_SSL` (`true` by default)
- `TABLEAU_AUTH_MODE` (`pat` or `password`)

Preferred PAT authentication:

- `TABLEAU_PAT_NAME`
- `TABLEAU_PAT_SECRET`

Username/password fallback:

- `TABLEAU_USERNAME`
- `TABLEAU_PASSWORD`

When interactive mode detects missing values, it asks for them and persists them in the **Windows user environment** (`HKCU\Environment`). Secrets use a hidden `getpass` prompt and are never printed.

> Security note: persistent environment variables are convenient for Task Scheduler but they are not an encrypted secret vault. Prefer a narrowly scoped Tableau Personal Access Token and a dedicated Windows account for scheduled execution. If stronger secret storage becomes a requirement, Windows Credential Manager or an enterprise vault is preferable.

## Run-input contract

The target group and the user list have deliberately different input rules:

- **Group name**
  - `--group "Existing Local Group"` for command-line / scheduler runs.
  - interactive prompt when `Run.cmd` or the notebook is used interactively.
- **Users**
  - users are always read from a file; direct `--users` / `--user` username arguments are not accepted.
  - `--users-file "D:\Automation\users.csv"` has highest precedence.
  - interactive mode prompts for a users-file path.
  - pressing Enter at that prompt, or omitting `--users-file` in a noninteractive run, falls back to the project root:
    1. `users.csv`
    2. `users.txt`
  - an explicitly supplied invalid path is an error; the program does not silently switch to a fallback file.

The project-root fallback is resolved from the repository location, not the current working directory, so Windows Task Scheduler can launch the script from another working directory safely.

## User-file format

Both `users.csv` and `users.txt` can contain a simple comma-separated list:

```text
alice,bob,carol
```

Multiple lines are also accepted:

```text
alice,bob
carol
```

Headered CSV remains supported. A column named `username`, `user`, `login`, or `name` is used:

```csv
username
alice
bob
carol
```

Usernames are trimmed and de-duplicated case-insensitively while preserving requested order.

Both `users.csv` and `users.txt` are git-ignored because real user lists should not be committed.

## Interactive Jupyter workflow

Open `tableau_bulk_add_users.ipynb`. The notebook imports the helpers rather than copying their source. It prompts for the existing local group name and users-file path, then shows:

1. selected users file and normalized requested-user list;
2. authentication status;
3. validation of the exact existing local group;
4. current membership count;
5. each attempted add and final per-user status;
6. a summary object you can inspect in later cells.

The first interactive run can bootstrap missing Tableau environment settings.

## CLI / scheduler

Run `Run.cmd`; it creates `.venv` and installs the pinned TSC dependency when needed.

Interactive run:

```bat
Run.cmd
```

You will be prompted for the group name and users-file path. If `users.csv` or `users.txt` exists in the project root, pressing Enter at the file prompt uses it.

Unattended scheduler with an explicit users file:

```bat
Run.cmd --group "My Local Group" --users-file "D:\Automation\tableau-users.csv"
```

Unattended scheduler using the project-root fallback:

```bat
Run.cmd --group "My Local Group"
```

Dry run:

```bat
Run.cmd --group "My Local Group" --users-file users.csv --dry-run
```

For Windows Task Scheduler, run the task under the same Windows account whose user environment contains the Tableau variables. Do **not** use `--interactive` or `--interactive-auth` for normal unattended runs.

## Tests

```bat
python -m pip install pytest
python -m pytest -q
```

The deterministic tests use a fake Tableau service, so orchestration behavior can be validated without spending API calls or requiring credentials.

## Prior art reviewed before implementation

This refactor intentionally inherits established Tableau automation patterns rather than inventing a custom HTTP client:

- Tableau's official `tableau/server-client-python` `create_group.py` sample: TSC authentication context management, pagination, and conflict-aware idempotency.
- Tableau REST API / TSC API reference: local group domain semantics and `groups.add_user` / `groups.add_users` behavior.
- `JVijeh/tableau-bulk-permissions-tutorial`: explicit step-by-step operational reporting and user-ID resolution before group assignment.
- `splnut/TabMgmt` `TableauService`: keep Tableau API access in a service layer instead of mixing it into UI/entry-point code.

The project deliberately does **not** inherit `.env` credential storage from some examples because this repository's contract is persistent Windows environment variables.
