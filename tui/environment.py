"""Small, dependency-free environment-file loading for local CLI providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import stat
import tempfile


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


@dataclass(frozen=True)
class EnvironmentSyncResult:
    """Safe, redacted outcome of copying shared values into a project env file."""

    succeeded: bool
    changed: bool = False
    message: str = ""
    values: dict[str, str] | None = None


def synchronize_env_file(
    source_path: Path,
    target_path: Path,
    shared_keys: tuple[str, ...],
    *,
    project_values: dict[str, str] | None = None,
    required_keys: tuple[str, ...] = (),
) -> EnvironmentSyncResult:
    """Synchronize selected values from a canonical env file into a target.

    The source is deliberately file-only: process variables are not consulted or
    written. Existing target values that disagree with the canonical source are
    conflicts, while blank values are safely filled. All validation happens before
    an atomic replacement, so a failure cannot leave a partially updated target.
    """
    source = source_path.expanduser().resolve()
    target = target_path.expanduser().resolve()
    values = read_env_file(source)
    required = tuple(dict.fromkeys(required_keys))
    missing = tuple(key for key in required if not values.get(key, "").strip())
    if missing:
        return EnvironmentSyncResult(
            False,
            message=(
                "Launch environment is missing required Supabase setting(s): "
                + ", ".join(missing)
                + "."
            ),
            values=values,
        )

    updates = {
        key: values[key]
        for key in shared_keys
        if values.get(key, "").strip()
    }
    for key, value in (project_values or {}).items():
        if value is not None and str(value).strip():
            updates[key] = str(value).strip()

    existing_text = ""
    if target.exists():
        if not target.is_file():
            return EnvironmentSyncResult(False, message="Project environment path is not a file.", values=values)
        try:
            existing_text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return EnvironmentSyncResult(False, message="Project environment file could not be read.", values=values)
    existing = read_env_file(target)
    missing_canonical_conflicts = tuple(
        key
        for key in shared_keys
        if existing.get(key, "").strip() and not values.get(key, "").strip()
    )
    if missing_canonical_conflicts:
        return EnvironmentSyncResult(
            False,
            message=(
                "Project environment has populated setting(s) absent from the launch "
                "environment: "
                + ", ".join(missing_canonical_conflicts)
                + ". Refusing to overwrite them."
            ),
            values=values,
        )
    conflicts = tuple(
        key for key, value in updates.items()
        if existing.get(key, "").strip() and existing[key].strip() != value
    )
    if conflicts:
        return EnvironmentSyncResult(
            False,
            message=(
                "Project environment has conflicting populated setting(s): "
                + ", ".join(conflicts)
                + ". Refusing to overwrite them."
            ),
            values=values,
        )

    updated_text = _update_env_text(existing_text, updates)
    if updated_text == existing_text:
        return EnvironmentSyncResult(True, values=values)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(target, updated_text)
    except OSError:
        return EnvironmentSyncResult(False, message="Project environment could not be updated atomically.", values=values)
    return EnvironmentSyncResult(True, changed=True, values=values)


_ENV_KEY_PATTERN = re.compile(r"^(?P<prefix>\s*(?:export\s+)?)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=")


def _update_env_text(text: str, updates: dict[str, str]) -> str:
    """Replace known assignments in place and append missing assignments."""
    if not updates:
        return text
    found: set[str] = set()
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        match = _ENV_KEY_PATTERN.match(line.rstrip("\r\n"))
        key = match.group("key") if match else None
        if key not in updates:
            result.append(line)
            continue
        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        prefix = match.group("prefix") or ""
        result.append(f"{prefix}{key}={_env_value(updates[key])}{newline}")
        found.add(key)
    newline = "\r\n" if "\r\n" in text else "\n"
    missing = [key for key in updates if key not in found]
    if missing:
        if result and result[-1] and not result[-1].endswith(("\n", "\r")):
            result.append(newline)
        result.extend(f"{key}={_env_value(updates[key])}{newline}" for key in missing)
    return "".join(result)


def _env_value(value: str) -> str:
    if any(character.isspace() for character in value) or "#" in value:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def _atomic_write(path: Path, text: str) -> None:
    """Replace one env file without exposing a partially written file."""
    temporary_path: Path | None = None
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    except OSError:
        try:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
