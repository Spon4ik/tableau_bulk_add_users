@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 (
  for %%V in (3.14 3.13 3.12 3.11 3.10) do (
    if not defined PYTHON_CMD py -%%V -c "import sys" >nul 2>&1 && set "PYTHON_CMD=py -%%V"
  )
)
if not defined PYTHON_CMD (
  where python >nul 2>&1
  if not errorlevel 1 python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo ERROR: Python 3.10 or newer was not found.
  exit /b 2
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PYTHON_CMD% -m venv .venv || exit /b 2
  ".venv\Scripts\python.exe" -m pip install --upgrade pip || exit /b 2
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || exit /b 2
)

if "%~1"=="" (
  echo Interactive mode: run inputs and missing authentication/server values will be prompted.
  ".venv\Scripts\python.exe" tableau_bulk_add_users.py --interactive
) else (
  ".venv\Scripts\python.exe" tableau_bulk_add_users.py %*
)
exit /b %ERRORLEVEL%
