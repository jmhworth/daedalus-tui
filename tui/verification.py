"""Local verification discovery and execution."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from threading import Thread
import time
from typing import Protocol


MAX_DIAGNOSTIC_CHARS = 64_000


class VerificationControl(Protocol):
    @property
    def stop_reason(self) -> str | None: ...


@dataclass(frozen=True)
class VerificationResult:
    succeeded: bool
    output: str


def discover_commands(root: Path, configured: list[list[str]]) -> list[list[str]]:
    if configured:
        return configured

    commands: list[list[str]] = []
    if package_has_test_script(root / "package.json"):
        commands.append(["npm", "test"])
    if (root / "tests").is_dir():
        commands.append([python_executable(root), "-m", "pytest"])

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if package_has_test_script(child / "package.json"):
            commands.append(["npm", "--prefix", child.name, "test"])
        if (child / "tests").is_dir():
            commands.append(
                [python_executable(child, root), "-m", "pytest", str(Path(child.name) / "tests")]
            )
    return commands


def python_executable(*roots: Path) -> str:
    """Resolve a Python interpreter that exists as a real file.

    Verification commands run without a shell, so a bare "python" fails outright on
    machines where it is only a shell alias or absent entirely. Prefer a virtual
    environment belonging to the code under test, then whatever is on PATH, and fall
    back to the interpreter running Daedalus itself.
    """
    for root in roots:
        for directory in (".venv", "venv"):
            candidate = venv_interpreter(root / directory)
            if candidate is not None:
                return candidate
    active = os.environ.get("VIRTUAL_ENV")
    if active:
        candidate = venv_interpreter(Path(active))
        if candidate is not None:
            return candidate
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return found
    return sys.executable


def venv_interpreter(directory: Path) -> str | None:
    """Return the interpreter inside a virtual environment directory, when usable."""
    relative = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    candidate = directory / relative
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def package_has_test_script(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    scripts = value.get("scripts") if isinstance(value, dict) else None
    return isinstance(scripts, dict) and isinstance(scripts.get("test"), str)


def run_verification(
    directory: Path,
    commands: list[list[str]],
    control: VerificationControl | None = None,
) -> VerificationResult:
    outputs: list[str] = []
    for command in commands:
        if control is not None and control.stop_reason is not None:
            return VerificationResult(False, "")
        try:
            if control is None:
                process = subprocess.run(command, cwd=directory, capture_output=True, text=True)
                output = format_process_result(command, process)
            else:
                return_code, stdout, stderr = _run_command_with_control(
                    command, directory, control
                )
                process = subprocess.CompletedProcess(command, return_code, stdout, stderr)
                output = format_process_result(command, process)
        except OSError as error:
            return VerificationResult(False, format_command_error(command, error))
        outputs.append(output)
        if process.returncode != 0:
            return VerificationResult(False, "\n\n".join(outputs))
    return VerificationResult(True, "\n\n".join(outputs))


def _run_command_with_control(
    command: list[str],
    directory: Path,
    control: VerificationControl,
) -> tuple[int | None, str, str]:
    """Run one verification command while honoring pause/cancel requests."""
    process = subprocess.Popen(
        command,
        cwd=directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=os.name == "posix",
    )
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def read_stream(stream, chunks: list[str]) -> None:
        if stream is None:
            return
        for chunk in iter(stream.readline, ""):
            if chunk:
                chunks.append(chunk)
        stream.close()

    readers = (
        Thread(target=read_stream, args=(process.stdout, stdout_chunks), daemon=True),
        Thread(target=read_stream, args=(process.stderr, stderr_chunks), daemon=True),
    )
    for reader in readers:
        reader.start()

    while process.poll() is None:
        if control.stop_reason is not None:
            _terminate_verification_process(process)
            break
        time.sleep(0.05)

    return_code = process.poll()
    if return_code is None:
        return_code = process.wait()
    for reader in readers:
        reader.join(timeout=2)
    return return_code, "".join(stdout_chunks), "".join(stderr_chunks)


def _terminate_verification_process(process: subprocess.Popen) -> None:
    """Terminate the verification process and its child process group."""
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()
    except (OSError, ProcessLookupError):
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()
        except (OSError, ProcessLookupError):
            process.kill()
        process.wait()


def truncate_diagnostic(text: str, limit: int = MAX_DIAGNOSTIC_CHARS) -> str:
    """Bound persisted diagnostics while retaining their beginning and end."""
    if len(text) <= limit:
        return text
    marker = f"\n\n[… diagnostic truncated from {len(text):,} to {limit:,} characters …]\n\n"
    budget = max(0, limit - len(marker))
    head = budget // 2
    tail = budget - head
    return text[:head] + marker + text[-tail:]


def format_command_error(command: list[str], error: OSError) -> str:
    """Describe a command that never started, which no code repair can fix."""
    message = f"COMMAND: {' '.join(command)}\nERROR: {error}"
    if isinstance(error, FileNotFoundError):
        message += (
            f"\n\nThe executable {command[0]!r} was not found on PATH. Verification runs "
            "without a shell, so shell aliases and functions do not apply. Install the "
            "executable or set verification_commands in the orchestration parameter file "
            "to a command that exists."
        )
    return message


def format_process_result(command: list[str], process: subprocess.CompletedProcess[str]) -> str:
    output = (
        f"COMMAND: {' '.join(command)}\n"
        f"STDOUT:\n{process.stdout}\nSTDERR:\n{process.stderr}"
    ).strip()
    return truncate_diagnostic(output)
