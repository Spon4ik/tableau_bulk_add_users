from __future__ import annotations

import getpass
import os
import sys
from dataclasses import dataclass
from typing import Callable

SERVER = "TABLEAU_SERVER_URL"
SITE = "TABLEAU_SITE_CONTENT_URL"
VERIFY_SSL = "TABLEAU_VERIFY_SSL"
PAT_NAME = "TABLEAU_PAT_NAME"
PAT_SECRET = "TABLEAU_PAT_SECRET"
USERNAME = "TABLEAU_ADMIN_USERNAME"
PASSWORD = "TABLEAU_ADMIN_PASSWORD"
AUTH_MODE = "TABLEAU_AUTH_MODE"

Prompt = Callable[[str], str]
SecretPrompt = Callable[[str], str]


@dataclass(frozen=True)
class TableauEnvironment:
    server_url: str
    site_content_url: str
    verify_ssl: bool
    auth_mode: str
    pat_name: str = ""
    pat_secret: str = ""
    username: str = ""
    password: str = ""


def _parse_bool(raw: str | None, default: bool = True) -> bool:
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{VERIFY_SSL} must be true or false")


def _registry_user_value(name: str) -> str | None:
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except FileNotFoundError:
        return None


def refresh_process_from_user_environment(names: list[str]) -> None:
    """Copy missing persistent Windows user-environment values into this process."""
    for name in names:
        if name in os.environ:
            continue
        value = _registry_user_value(name)
        if value is not None:
            os.environ[name] = value


def persist_user_environment(name: str, value: str) -> None:
    """Persist a Windows user environment variable without exposing it on a command line."""
    os.environ[name] = value
    if sys.platform != "win32":
        raise RuntimeError("Persistent system environment setup is supported on Windows only")

    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def _prompt_nonempty(label: str, prompt: Prompt) -> str:
    while True:
        value = prompt(label).strip()
        if value:
            return value
        print("A value is required.")


def _broadcast_environment_change() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    result = ctypes.c_size_t()
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, ctypes.byref(result)
    )


def _save(values: dict[str, str]) -> None:
    for name, value in values.items():
        persist_user_environment(name, value)
    _broadcast_environment_change()
    print("Saved persistent Windows user environment variables: " + ", ".join(values))
    print("Values were also loaded into the current Python process.")


def ensure_environment(
    *,
    interactive: bool,
    prompt: Prompt = input,
    secret_prompt: SecretPrompt = getpass.getpass,
) -> TableauEnvironment:
    """Load Tableau configuration, prompting and persisting missing values when allowed."""
    names = [SERVER, SITE, VERIFY_SSL, AUTH_MODE, PAT_NAME, PAT_SECRET, USERNAME, PASSWORD]
    refresh_process_from_user_environment(names)

    server = os.getenv(SERVER, "").strip()
    site_present = SITE in os.environ
    site = os.getenv(SITE, "").strip()
    verify_present = VERIFY_SSL in os.environ
    auth_mode = os.getenv(AUTH_MODE, "").strip().casefold()

    # Backward compatibility with the initial script: infer auth mode from populated pairs.
    if not auth_mode:
        if os.getenv(PAT_NAME, "").strip() and os.getenv(PAT_SECRET, "").strip():
            auth_mode = "pat"
        elif os.getenv(USERNAME, "").strip() and os.getenv(PASSWORD, ""):
            auth_mode = "password"

    missing_base = []
    if not server:
        missing_base.append(SERVER)

    if not interactive and (missing_base or not auth_mode):
        missing = missing_base + ([] if auth_mode else [AUTH_MODE])
        raise ValueError("Missing required Tableau environment configuration: " + ", ".join(missing))

    to_save: dict[str, str] = {}
    if not server:
        server = _prompt_nonempty("Tableau server URL (for example https://tableau.example.com): ", prompt)
        to_save[SERVER] = server
    if not site_present:
        site = prompt("Tableau site content URL [blank = Default site]: ").strip()
        to_save[SITE] = site
    if not verify_present:
        to_save[VERIFY_SSL] = "true"

    if not auth_mode:
        choice = prompt("Authentication method [PAT/password] (default PAT): ").strip().casefold() or "pat"
        if choice not in {"pat", "password"}:
            raise ValueError("Authentication method must be PAT or password")
        auth_mode = choice
        to_save[AUTH_MODE] = auth_mode

    if auth_mode == "pat":
        pat_name = os.getenv(PAT_NAME, "").strip()
        pat_secret = os.getenv(PAT_SECRET, "")
        if not pat_name or not pat_secret:
            if not interactive:
                missing = [name for name, value in ((PAT_NAME, pat_name), (PAT_SECRET, pat_secret)) if not value]
                raise ValueError("Missing required Tableau environment configuration: " + ", ".join(missing))
            if not pat_name:
                pat_name = _prompt_nonempty("Tableau Personal Access Token name: ", prompt)
                to_save[PAT_NAME] = pat_name
            if not pat_secret:
                pat_secret = secret_prompt("Tableau Personal Access Token secret: ")
                if not pat_secret:
                    raise ValueError("PAT secret cannot be empty")
                to_save[PAT_SECRET] = pat_secret
        username = password = ""
    elif auth_mode == "password":
        username = os.getenv(USERNAME, "").strip()
        password = os.getenv(PASSWORD, "")
        if not username or not password:
            if not interactive:
                missing = [name for name, value in ((USERNAME, username), (PASSWORD, password)) if not value]
                raise ValueError("Missing required Tableau environment configuration: " + ", ".join(missing))
            if not username:
                username = _prompt_nonempty("Tableau username: ", prompt)
                to_save[USERNAME] = username
            if not password:
                password = secret_prompt("Tableau password: ")
                if not password:
                    raise ValueError("Password cannot be empty")
                to_save[PASSWORD] = password
        pat_name = pat_secret = ""
    else:
        raise ValueError(f"Unsupported {AUTH_MODE}: {auth_mode!r}")

    if to_save:
        _save(to_save)

    return TableauEnvironment(
        server_url=server,
        site_content_url=site,
        verify_ssl=_parse_bool(os.getenv(VERIFY_SSL), True),
        auth_mode=auth_mode,
        pat_name=pat_name,
        pat_secret=pat_secret,
        username=username,
        password=password,
    )
