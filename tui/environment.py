"""Small, dependency-free environment-file loading for local CLI providers."""

from __future__ import annotations

from pathlib import Path
import os


def cursor_environment(directory: Path, extra_files: tuple[Path, ...] = ()) -> dict[str, str]:
    """Return the process environment plus local Cursor credentials.

    Explicit process variables always win over values in `.env` files. The
    target repository's `.env` is checked before the standalone TUI's `.env`.
    """
    environment = os.environ.copy()
    package_root = Path(__file__).resolve().parents[1]
    paths = (directory / ".env", *extra_files, package_root / ".env")
    seen: set[Path] = set()
    for path in paths:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        for key, value in read_env_file(path).items():
            environment.setdefault(key, value)
    return environment


def agent_environment(
    provider: str,
    directory: Path,
    extra_files: tuple[Path, ...] = (),
    stripped_variables: tuple[str, ...] = (),
) -> dict[str, str] | None:
    """Return the subprocess environment for one provider, or None to inherit.

    Cursor reads its credentials from local `.env` files. Other providers load
    only explicitly supplied environment files into their subprocess
    environment, without placing a copy in the isolated worktree. Every
    provider additionally has ``stripped_variables`` removed so account mode
    cannot accidentally bill an API key from one of those files.
    """
    if provider == "cursor":
        environment = cursor_environment(directory, extra_files)
    elif stripped_variables or extra_files:
        environment = os.environ.copy()
        for path in extra_files:
            for key, value in read_env_file(path).items():
                environment.setdefault(key, value)
    else:
        # Nothing to change; let the child inherit the parent environment.
        return None
    for variable in stripped_variables:
        environment.pop(variable, None)
    return environment


def read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        key, separator, value = stripped.partition("=")
        if not separator or not key or any(character.isspace() for character in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values
