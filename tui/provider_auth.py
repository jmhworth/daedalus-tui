"""Provider sign-in status checks for the settings bar.

Account mode lets agents run on the operator's own plan instead of API credit,
which only works while the provider CLI is signed in. The TUI cannot host an
interactive login itself: a child CLI that takes over the terminal makes the
Textual application appear to vanish. These helpers therefore report status and
hand the operator the exact command to run in their own shell.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import TYPE_CHECKING

from .debug_log import LOGGER

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from .config import ProviderAuthSettings


STATUS_TIMEOUT_SECONDS = 15.0
DIAGNOSTIC_LIMIT = 2_000


@dataclass(frozen=True)
class AuthStatus:
    """Outcome of one provider status check.

    ``signed_in`` is ``None`` when the check could not reach a verdict, which is
    different from a confirmed signed-out account and must not be reported as one.
    """

    provider: str
    label: str
    signed_in: bool | None
    detail: str
    sign_in_command: tuple[str, ...] = ()
    executable_available: bool = True

    @property
    def summary(self) -> str:
        if not self.executable_available:
            return f"{self.label}: CLI not installed"
        if self.signed_in is None:
            return f"{self.label}: sign-in status unknown"
        return f"{self.label}: {'signed in' if self.signed_in else 'signed out'}"

    @property
    def sign_in_hint(self) -> str:
        if not self.sign_in_command:
            return ""
        return " ".join(self.sign_in_command)


def check_provider_auth(
    provider: str,
    settings: "ProviderAuthSettings",
    directory: Path | None = None,
    run_process=None,
    find_executable=None,
) -> AuthStatus:
    """Run a provider's status command and report whether it is signed in.

    The subprocess hooks resolve here rather than as argument defaults so tests
    can patch this module's ``subprocess`` and ``shutil`` names.
    """
    run_process = run_process or subprocess.run
    find_executable = find_executable or shutil.which
    command = tuple(settings.status_command)
    sign_in_command = tuple(settings.sign_in_command)
    if not command:
        return AuthStatus(
            provider,
            settings.label,
            None,
            "No status command is configured for this provider.",
            sign_in_command,
        )

    if find_executable(command[0]) is None:
        return AuthStatus(
            provider,
            settings.label,
            None,
            f"`{command[0]}` is not on PATH. Install the CLI to sign in.",
            sign_in_command,
            executable_available=False,
        )

    try:
        completed = run_process(
            list(command),
            cwd=str(directory) if directory is not None else None,
            capture_output=True,
            text=True,
            shell=False,
            timeout=STATUS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        LOGGER.warning("Provider status check timed out provider=%s", provider)
        return AuthStatus(
            provider,
            settings.label,
            None,
            f"`{' '.join(command)}` did not respond within "
            f"{STATUS_TIMEOUT_SECONDS:g} seconds.",
            sign_in_command,
        )
    except (OSError, subprocess.SubprocessError) as error:
        LOGGER.warning("Provider status check failed provider=%s error=%s", provider, error)
        return AuthStatus(provider, settings.label, None, str(error), sign_in_command)

    detail = "\n".join(
        part.strip() for part in (completed.stdout, completed.returncode and completed.stderr or "") if part.strip()
    )
    return AuthStatus(
        provider,
        settings.label,
        completed.returncode == 0,
        detail[-DIAGNOSTIC_LIMIT:] or f"`{' '.join(command)}` exited with {completed.returncode}.",
        sign_in_command,
    )


def sign_in_instructions(status: AuthStatus, account_login: bool) -> str:
    """Return the operator-facing guidance shown in the sign-in dialog."""
    if not account_login:
        return (
            f"{status.label} is running in API-key mode. Agents use the provider's API key "
            "from the process environment or a local .env file, which bills API credit "
            "rather than your plan.\n\n"
            "Set auth.mode = \"account\" in parameter_files/daedalus-tui.toml to run agents "
            "on your signed-in account instead."
        )
    if not status.executable_available:
        return (
            f"{status.label} is not installed.\n\n{status.detail}\n\n"
            "Install the CLI, then run the sign-in command below."
        )

    lead = {
        True: f"{status.label} is signed in. Agents run on this account's plan.",
        False: f"{status.label} is not signed in, so agent runs will fail.",
        None: f"{status.label} sign-in status could not be determined.",
    }[status.signed_in]

    if not status.sign_in_command:
        return f"{lead}\n\n{status.detail}"
    return (
        f"{lead}\n\n{status.detail}\n\n"
        "Sign in from your own terminal — the TUI cannot host an interactive login "
        "without taking over this screen:\n\n"
        f"    {status.sign_in_hint}\n\n"
        "Then choose Check again."
    )


__all__ = ["AuthStatus", "check_provider_auth", "sign_in_instructions"]
