# Tableau Bulk Add Users

Add **existing Tableau site users** to an **existing local Tableau group**, with the same reusable orchestration available from Jupyter and unattended Windows Task Scheduler runs.

## Design

The repository follows the patterns used by Tableau's official `tableauserverclient` (TSC) samples: TSC handles REST API version negotiation and pagination, membership is checked before mutation, and Tableau's `409011` "already in group" response is treated as an idempotent state rather than a fatal error.

The important architectural rule is that business logic lives under `helpers/`. The notebook and CLI are only front ends.

- `helpers/environment.py` — persistent Windows user-environment configuration and interactive credential bootstrap.
- `helpers/tableau_service.py` — thin TSC adapter.
- `helpers/orchestrator.py` — step-by-step workflow and per-user statuses.
- `helpers/user_input.py` — TXT/CSV/list parsing and de-duplication.
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

When interactive mode detects missing values, it asks for them and persists them in the **Windows user environment** (`HKCU\\Environment`). Secrets use a hidden `getpass` prompt and are never printed.

> Security note: persistent environment variables are convenient for Task Scheduler but they are not an encrypted secret vault. Prefer a narrowly scoped Tableau Personal Access Token and a dedicated Windows account for scheduled execution. If stronger secret storage becomes a requirement, Windows Credential Manager or an enterprise vault is preferable.

## Interactive Jupyter workflow

Open `tableau_bulk_add_users.ipynb`. The notebook imports the helpers rather than copying their source. A normal run shows:

1. authentication status;
2. the normalized requested-user list;
3. validation of the exact existing local group;
4. current membership count;
5. each attempted add and final per-user status;
6. a summary object you can inspect in later cells.

The first interactive run can bootstrap missing Tableau environment settings.

## CLI / scheduler

Install once by simply running `Run.cmd`; it creates `.venv` and installs the pinned TSC dependency when needed.

Interactive first-time setup (either enter run inputs interactively or provide them on the command line):

```bat
Run.cmd

Run.cmd --group "My Local Group" --users "alice,bob" --interactive-auth
```

Unattended scheduler run:

```bat
Run.cmd --group "My Local Group" --users-file "D:\\Automation\\tableau-users.csv"
```

Dry run:

```bat
Run.cmd --group "My Local Group" --users-file users.csv --dry-run
```

For Windows Task Scheduler, run the task under the same Windows account whose user environment contains the Tableau variables. The scheduled path should pass `--group` and `--users-file`; it should **not** pass `--interactive-auth`.

## User files

TXT supports one username per line or comma-separated values. CSV accepts a column named `username`, `user`, `login`, or `name`. Usernames are trimmed and de-duplicated case-insensitively while preserving the requested order.

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
