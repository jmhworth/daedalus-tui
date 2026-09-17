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


def read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
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


def redact_environment_values(message: str, environment: dict[str, str] | None = None) -> str:
    """Remove values loaded for a subprocess from a user-facing diagnostic."""
    redacted = str(message)
    sensitive_values = [
        value
        for key, value in (environment or {}).items()
        if value and any(token in key.upper() for token in ("KEY", "TOKEN", "PASSWORD", "SECRET", "URL"))
    ]
    for value in sorted(sensitive_values, key=len, reverse=True):
        if value:
            redacted = redacted.replace(value, "[redacted]")
    return redacted
