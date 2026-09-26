"""Personal shared-Supabase scaffold (Phase 1) and ecosystem Activate (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterator

from .environment import read_env_file, redact_environment_values
from .project_config import DAEDALUS_CONFIG_FILENAME
from .supabase_migrations import push_migrations

TUI_ROOT = Path(__file__).resolve().parents[1]
PARAMETER_PATH = TUI_ROOT / "parameter_files" / "daedalus-tui-personal-supabase.toml"
PROFILE_RELATIVE_PATHS = (
    Path(".agents") / "profiles" / "coding.md",
    Path(".agents") / "profiles" / "architecture.md",
)
SECTION_TABLE = "personal_supabase"

# Activation outcome classes stored in the marker (never credentials).
ACTIVATE_STATUS_SUCCESS = "success"
ACTIVATE_STATUS_BLOCKED_GIT = "blocked_git"
ACTIVATE_STATUS_BLOCKED_SUPABASE = "blocked_supabase"
ACTIVATE_STATUS_BLOCKED_SCAFFOLD = "blocked_scaffold"


def _validate_schema_name(schema: object, maximum_length: int) -> str:
    # Imported lazily to avoid a circular import with project_initializer.
    from .project_initializer import validate_project_name

    return validate_project_name(schema, maximum_length)


@dataclass(frozen=True)
class PersonalSupabaseStatus:
    """Registration / activation marker loaded from a target project's ``.daedalus``."""

    registered: bool
    schema: str | None = None
    activated: bool = False
    last_activate_status: str | None = None
    last_activate_error: str | None = None


@dataclass(frozen=True)
class RegistrationResult:
    """Outcome of scaffolding personal-Supabase files into a project tree."""

    status: str
    schema: str
    message: str
    project_root: Path
    already_registered: bool = False


@dataclass(frozen=True)
class PersonalSupabaseBootstrapResult:
    """Redacted result of preparing one registered project for launch use."""

    status: str
    project_root: Path
    schema: str | None = None
    project_ref: str | None = None
    message: str = ""
    environment: dict[str, str] | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ActivationResult:
    """Outcome of Phase 2 Activate (and optional Phase 1 scaffold)."""

    status: str
    schema: str
    message: str
    project_root: Path
    activated: bool = False
    scaffolded: bool = False
    committed: bool = False
    blocked_reason: str | None = None


@dataclass(frozen=True)
class PreflightResult:
    """Outcome of the access-method-aware live Supabase connectivity probe."""

    succeeded: bool
    message: str = ""
    method: str = ""


@dataclass(frozen=True)
class GitScaffoldCommitResult:
    """Outcome of the operating-branch Git gate and software-owned scaffold commit."""

    succeeded: bool
    message: str = ""
    committed: bool = False


@dataclass(frozen=True)
class PersonalSupabaseRemovalResult:
    """Outcome of removing the local personal-Supabase integration artifacts."""

    succeeded: bool
    message: str
    project_root: Path
    removed_paths: tuple[str, ...] = ()


def personal_supabase_environment_settings(settings: dict | None = None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return canonical and required environment keys from the feature parameters."""
    values = settings or load_personal_supabase_settings()
    canonical = tuple(str(key) for key in values["canonical_env_keys"])
    required = tuple(str(key) for key in values["required_env_keys"])
    return canonical, required


def personal_supabase_managed_env_keys(settings: dict | None = None) -> set[str]:
    """Return every env key this feature may clean up (preferred + aliases)."""
    values = settings or load_personal_supabase_settings()
    keys = {
        str(values["env_schema_key"]),
        str(values["env_url_key"]),
        str(values["env_project_ref_key"]),
        str(values["env_publishable_key"]),
        str(values["env_secret_key"]),
        str(values["env_db_url_key"]),
        str(values["env_access_token_key"]),
        *(str(key) for key in values.get("env_publishable_key_aliases", [])),
        *(str(key) for key in values.get("env_secret_key_aliases", [])),
        *(str(key) for key in values["canonical_env_keys"]),
    }
    return keys


def load_personal_supabase_settings() -> dict:
    """Load tunables for schema registration from the paired parameter file."""
    with PARAMETER_PATH.open("rb") as source:
        return tomllib.load(source)


def project_ref_from_supabase_url(url: str) -> str | None:
    """Derive the project ref from a standard ``https://<ref>.supabase.co`` URL."""
    parsed = urlparse(str(url).strip())
    host = (parsed.hostname or "").lower()
    suffix = ".supabase.co"
    if not host.endswith(suffix):
        return None
    ref = host[: -len(suffix)]
    if not ref or "." in ref or not re.fullmatch(r"[a-z0-9_-]+", ref):
        return None
    return ref


def resolve_project_ref_from_environment(
    values: dict[str, str],
    settings: dict | None = None,
) -> str:
    """Return an explicit or URL-derived project ref (empty when neither is usable)."""
    config = settings or load_personal_supabase_settings()
    explicit = values.get(str(config["env_project_ref_key"]), "").strip()
    if explicit:
        return explicit
    url = values.get(str(config["env_url_key"]), "").strip()
    return project_ref_from_supabase_url(url) or ""


def resolve_personal_supabase_environment(
    values: dict[str, str],
    settings: dict | None = None,
    *,
    require_database_access: bool = True,
) -> tuple[dict[str, str] | None, str | None]:
    """Normalize project env into preferred keys, accepting aliases.

    Returns ``(overlay, None)`` on success. The overlay always uses preferred
    names (``SUPABASE_PUBLISHABLE_KEY``, ``SUPABASE_SECRET_KEY``, derived
    ``SUPABASE_PROJECT_REF`` when possible). Legacy anon/service_role and
    ``SUPABASE_PRIVATE_KEY`` remain accepted as inputs.
    """
    config = settings or load_personal_supabase_settings()
    url_key = str(config["env_url_key"])
    publishable_key = str(config["env_publishable_key"])
    secret_key = str(config["env_secret_key"])
    project_ref_key = str(config["env_project_ref_key"])
    db_url_key = str(config["env_db_url_key"])
    access_token_key = str(config["env_access_token_key"])

    url = values.get(url_key, "").strip()
    if not url:
        return None, f"Project environment is missing required Supabase setting(s): {url_key}."

    publishable_candidates = [publishable_key, *(str(k) for k in config.get("env_publishable_key_aliases", []))]
    secret_candidates = [secret_key, *(str(k) for k in config.get("env_secret_key_aliases", []))]
    _, publishable = _first_filled_env_value(values, publishable_candidates)
    _, secret = _first_filled_env_value(values, secret_candidates)
    missing: list[str] = []
    if not publishable:
        missing.append(_key_or_aliases_label(publishable_candidates))
    if not secret:
        missing.append(_key_or_aliases_label(secret_candidates))
    if missing:
        return None, (
            "Project environment is missing required Supabase setting(s): "
            + ", ".join(missing)
            + "."
        )

    project_ref = resolve_project_ref_from_environment(values, config)
    if not project_ref:
        return None, (
            "Project environment needs a Supabase project ref: set "
            f"{project_ref_key}, or use a {url_key} of the form "
            "https://<project-ref>.supabase.co."
        )
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project_ref):
        return None, "Project environment has a malformed Supabase project ref."

    db_url = values.get(db_url_key, "").strip()
    access_token = values.get(access_token_key, "").strip()
    if require_database_access and not db_url and not access_token:
        return None, (
            "Project environment must define one database access setting: "
            f"{db_url_key} or {access_token_key}. "
            "API keys alone cannot run migration pushes."
        )

    overlay = {
        url_key: url,
        publishable_key: publishable,
        secret_key: secret,
        project_ref_key: project_ref,
    }
    if db_url:
        overlay[db_url_key] = db_url
    if access_token:
        overlay[access_token_key] = access_token
    return overlay, None


def _first_filled_env_value(values: dict[str, str], keys: list[str]) -> tuple[str, str]:
    for key in keys:
        value = values.get(key, "").strip()
        if value:
            return key, value
    return "", ""


def _key_or_aliases_label(keys: list[str]) -> str:
    if len(keys) == 1:
        return keys[0]
    return f"{keys[0]} (or {' / '.join(keys[1:])})"


def schema_from_project_root(project_root: Path, maximum_length: int | None = None) -> str:
    """Derive and validate the Postgres schema name from the project directory slug."""
    settings = load_personal_supabase_settings()
    limit = int(maximum_length if maximum_length is not None else settings["maximum_schema_name_length"])
    return _validate_schema_name(project_root.resolve().name, limit)


def personal_supabase_scaffold_relative_paths(
    schema: str,
    settings: dict | None = None,
) -> tuple[str, ...]:
    """Return repository-relative paths owned by personal-Supabase scaffolding."""
    values = settings or load_personal_supabase_settings()
    return (
        "supabase/config.toml",
        f"supabase/migrations/{values['migration_filename']}",
        ".env.example",
        str(PROFILE_RELATIVE_PATHS[0]),
        str(PROFILE_RELATIVE_PATHS[1]),
        DAEDALUS_CONFIG_FILENAME,
    )


def remove_personal_supabase(project_root: Path) -> PersonalSupabaseRemovalResult:
    """Remove local personal-Supabase artifacts without touching remote state.

    The Supabase directory is owned wholly by this feature and is removed in
    full. Shared project files are edited surgically: the personal marker table,
    generated env assignments, and generated profile sections are removed while
    unrelated project configuration and guidance remain intact. The ignored
    project ``.env`` is reduced to non-Supabase settings rather than deleting
    unrelated application credentials.
    """
    root = project_root.expanduser().resolve()
    settings = load_personal_supabase_settings()
    removed: list[str] = []
    failures: list[str] = []

    def record(path: Path, operation: Callable[[], bool]) -> None:
        try:
            changed = operation()
        except (OSError, UnicodeError) as error:
            failures.append(f"{path.relative_to(root)}: {error}")
            return
        if changed:
            removed.append(str(path.relative_to(root)))

    supabase = root / "supabase"
    if supabase.is_symlink():
        record(supabase, lambda: _remove_path(supabase))
    elif supabase.is_dir():
        record(supabase, lambda: _remove_path(supabase))
    elif supabase.exists():
        failures.append("supabase: expected a directory, so it was left untouched")

    marker = root / DAEDALUS_CONFIG_FILENAME
    record(marker, lambda: _remove_personal_supabase_marker(marker))

    env_example = root / ".env.example"
    record(env_example, lambda: _remove_personal_supabase_env_example(env_example))

    project_env = root / ".env"
    record(project_env, lambda: _remove_personal_supabase_env_values(project_env, settings))

    for relative in PROFILE_RELATIVE_PATHS:
        profile = root / relative
        record(profile, lambda profile=profile: _remove_personal_supabase_profile(profile, settings))

    if failures:
        message = "Personal Supabase cleanup was incomplete: " + "; ".join(failures)
        return PersonalSupabaseRemovalResult(False, message, root, tuple(removed))
    if not removed:
        return PersonalSupabaseRemovalResult(True, "No local personal Supabase artifacts were found.", root)
    return PersonalSupabaseRemovalResult(
        True,
        f"Removed local personal Supabase artifacts ({', '.join(removed)}).",
        root,
        tuple(removed),
    )


def _remove_personal_supabase_marker(path: Path) -> bool:
    """Remove only the personal-Supabase table from a project marker."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"(?ms)^\[{re.escape(SECTION_TABLE)}\]\n.*?(?=^\[|\Z)")
    match = pattern.search(text)
    if match is None:
        return False
    updated = _remove_text_span(text, match.start(), match.end())
    if updated.strip():
        path.write_text(updated, encoding="utf-8")
    else:
        path.unlink()
    return True


def _remove_path(path: Path) -> bool:
    """Remove one already-resolved file, symlink, or directory."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        return False
    return True


def _remove_personal_supabase_env_example(path: Path) -> bool:
    """Remove the generated shared-Supabase block from ``.env.example``."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    updated = text
    start_marker = "# Shared personal Supabase project."
    start = next(
        (match.start() for match in re.finditer(rf"(?m)^{re.escape(start_marker)}.*$", updated)),
        None,
    )
    if start is not None:
        end_match = re.search(
            r"(?m)^# After migrations apply, allow-list schema .*$",
            updated[start:],
        )
        if end_match is not None:
            end = start + end_match.end()
            updated = _remove_text_span(updated, start, end)

    # Older or hand-edited examples may have the schema assignments without
    # the generated block marker; remove those assignments too.
    updated = re.sub(
        r"(?m)^# After migrations apply, allow-list schema .*$\n?",
        "",
        updated,
    )
    updated = _without_personal_supabase_env_values(updated)
    if updated == text:
        return False
    if updated.strip():
        path.write_text(updated, encoding="utf-8")
    else:
        path.unlink()
    return True


def _remove_personal_supabase_env_values(path: Path, settings: dict) -> bool:
    """Remove synchronized Supabase assignments while preserving other env values."""
    if not path.is_file():
        return False
    keys = personal_supabase_managed_env_keys(settings)
    text = path.read_text(encoding="utf-8")
    updated = _without_personal_supabase_env_values(text, keys)
    if updated == text:
        return False
    if updated.strip():
        path.write_text(updated, encoding="utf-8")
    else:
        path.unlink()
    return True


def _without_personal_supabase_env_values(text: str, keys: set[str] | None = None) -> str:
    """Return env text without the configured Supabase assignments."""
    if keys is None:
        keys = personal_supabase_managed_env_keys()
    lines = text.splitlines(keepends=True)
    assignment = re.compile(r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=")
    return "".join(
        line
        for line in lines
        if not ((match := assignment.match(line.rstrip("\r\n"))) and match.group("key") in keys)
    )


def _remove_personal_supabase_profile(path: Path, settings: dict) -> bool:
    """Remove the generated Personal Supabase section from one profile."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    heading = str(settings["profile_section_heading"])
    pattern = re.compile(rf"(?ms)^{re.escape(heading)}\n.*?(?=^## |\Z)")
    match = pattern.search(text)
    if match is None:
        return False
    updated = _remove_text_span(text, match.start(), match.end())
    if updated.strip():
        path.write_text(updated, encoding="utf-8")
    else:
        path.unlink()
    return True


def _remove_text_span(text: str, start: int, end: int) -> str:
    """Remove a generated block and normalize the blank lines around it."""
    before = text[:start].rstrip()
    after = text[end:].lstrip()
    if before and after:
        return f"{before}\n\n{after.rstrip()}\n"
    if before:
        return f"{before}\n"
    if after:
        return f"{after.rstrip()}\n"
    return ""


def load_personal_supabase_status(project_root: Path) -> PersonalSupabaseStatus:
    """Return the ``[personal_supabase]`` marker, or an unregistered default."""
    path = project_root / DAEDALUS_CONFIG_FILENAME
    if not path.is_file():
        return PersonalSupabaseStatus(registered=False)
    try:
        with path.open("rb") as source:
            values = tomllib.load(source)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"Could not read project configuration {path}: {error}") from error

    table = values.get(SECTION_TABLE, {})
    if table in (None, {}):
        return PersonalSupabaseStatus(registered=False)
    if not isinstance(table, dict):
        raise ValueError(f"{path} {SECTION_TABLE} must be a table.")

    registered = table.get("registered", False)
    if not isinstance(registered, bool):
        raise ValueError(f"{path} {SECTION_TABLE}.registered must be a boolean.")
    schema = table.get("schema")
    if schema is not None and (not isinstance(schema, str) or not schema.strip()):
        raise ValueError(f"{path} {SECTION_TABLE}.schema must be a non-empty string when set.")
    activated = table.get("activated", False)
    if not isinstance(activated, bool):
        raise ValueError(f"{path} {SECTION_TABLE}.activated must be a boolean.")
    last_status = table.get("last_activate_status")
    if last_status is not None and (not isinstance(last_status, str) or not last_status.strip()):
        raise ValueError(
            f"{path} {SECTION_TABLE}.last_activate_status must be a non-empty string when set."
        )
    last_error = table.get("last_activate_error")
    if last_error is not None and not isinstance(last_error, str):
        raise ValueError(f"{path} {SECTION_TABLE}.last_activate_error must be a string when set.")
    return PersonalSupabaseStatus(
        registered=registered,
        schema=schema.strip() if isinstance(schema, str) else None,
        activated=activated,
        last_activate_status=last_status.strip() if isinstance(last_status, str) else None,
        last_activate_error=last_error if isinstance(last_error, str) else None,
    )


def project_personal_supabase_env_path(project_root: Path) -> Path:
    """Return the project-local ``.env`` path operators must edit."""
    return project_root.expanduser().resolve() / ".env"


def load_project_personal_supabase_env_values(project_root: Path) -> dict[str, str]:
    """Load values from the project ``.env`` only (no process overrides).

    Wizard Continue uses :func:`probe_project_personal_supabase_environment` so the
    TUI never needs these values just to gate setup. Activate/bootstrap still load
    the file when building CLI environments.
    """
    return read_env_file(project_personal_supabase_env_path(project_root))


def probe_project_personal_supabase_environment(
    project_root: Path,
    *,
    require_database_access: bool = True,
    run_process=subprocess.run,
    timeout_seconds: float = 30.0,
) -> tuple[bool, str | None]:
    """Check required project Supabase keys via a child process exit code.

    The parent only observes the exit code and a key-name diagnostic on failure.
    Secret values stay inside the probe process (cwd = project root).
    """
    project = project_root.expanduser().resolve()
    env = {
        **os.environ,
        "DAEDALUS_ENV_PROBE_REQUIRE_DB": "1" if require_database_access else "0",
    }
    # cwd is the project root (not the package), so keep the TUI importable.
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = (
        f"{TUI_ROOT}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(TUI_ROOT)
    )
    try:
        process = run_process(
            [sys.executable, "-m", "tui.env_presence_probe"],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return False, "Project environment presence probe timed out."
    except OSError as error:
        return False, f"Project environment presence probe failed to start: {error}."
    if process.returncode == 0:
        return True, None
    message = (process.stderr or process.stdout or "").strip()
    return False, message or "Project environment could not be validated."


def validate_project_personal_supabase_environment(
    project_root: Path,
    *,
    require_database_access: bool = True,
    settings: dict | None = None,
) -> tuple[dict[str, str] | None, str | None]:
    """Read and resolve the project ``.env`` without writing any files.

    Returns ``(environment, None)`` on success. The environment merges file
    values with preferred/derived keys for CLI use. On failure returns
    ``(file_values_or_None, error)``.

    Prefer :func:`probe_project_personal_supabase_environment` when only a
    presence check is needed (wizard Continue) so the TUI process never loads
    secret values just to gate the next step.
    """
    config = settings or load_personal_supabase_settings()
    source_values = load_project_personal_supabase_env_values(project_root)
    resolved, resolve_error = resolve_personal_supabase_environment(
        source_values,
        config,
        require_database_access=require_database_access,
    )
    if resolve_error or resolved is None:
        return source_values, resolve_error or "Project environment could not be resolved."
    return {**source_values, **resolved}, None


def bootstrap_personal_supabase(
    project_root: Path,
    *,
    require_database_access: bool = True,
) -> PersonalSupabaseBootstrapResult:
    """Validate registration and the project-local shared environment.

    This helper performs no remote operation and never writes ``.env`` files.
    It only confirms the tracked Supabase scaffold and that project-local
    credentials can be used by the orchestration-owned CLI push.
    """
    root = project_root.expanduser().resolve()
    settings = load_personal_supabase_settings()
    try:
        status = load_personal_supabase_status(root)
    except ValueError as error:
        return PersonalSupabaseBootstrapResult("failed", root, message=str(error))
    if not status.registered:
        return PersonalSupabaseBootstrapResult("skipped", root, message="Project is not registered.")
    if status.schema is None:
        return PersonalSupabaseBootstrapResult("failed", root, message="Registered project has no schema marker.")
    try:
        schema = _validate_schema_name(status.schema, int(settings["maximum_schema_name_length"]))
    except ValueError as error:
        return PersonalSupabaseBootstrapResult("failed", root, message=f"Invalid registered schema: {error}")
    if schema != status.schema:
        return PersonalSupabaseBootstrapResult("failed", root, schema=schema, message="Registered schema marker is not canonical.")

    environment, resolve_error = validate_project_personal_supabase_environment(
        root,
        require_database_access=require_database_access,
        settings=settings,
    )
    if resolve_error or environment is None:
        return PersonalSupabaseBootstrapResult(
            "failed",
            root,
            schema=schema,
            message=resolve_error or "Project environment could not be resolved.",
            environment=environment,
        )
    project_ref = environment.get(str(settings["env_project_ref_key"]), "").strip()
    scaffold_error = _validate_supabase_scaffold(root, schema, settings, project_ref)
    if scaffold_error:
        return PersonalSupabaseBootstrapResult("failed", root, schema=schema, message=scaffold_error)
    return PersonalSupabaseBootstrapResult(
        "success",
        root,
        schema=schema,
        project_ref=project_ref,
        message="Project Supabase environment validated.",
        environment=environment,
    )


def _validate_supabase_scaffold(
    root: Path,
    schema: str,
    settings: dict,
    project_ref: str = "",
) -> str | None:
    supabase = root / "supabase"
    migrations = supabase / "migrations"
    config_path = supabase / "config.toml"
    migration_path = migrations / str(settings["migration_filename"])
    if not supabase.is_dir() or not config_path.is_file() or not migrations.is_dir():
        return "Personal Supabase scaffold is incomplete; expected supabase/config.toml and supabase/migrations/."
    if not migration_path.is_file():
        return f"Personal Supabase scaffold is missing {migration_path.relative_to(root)}."
    try:
        migration_text = migration_path.read_text(encoding="utf-8")
        config_values = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        return f"Personal Supabase scaffold could not be read: {error}"
    if not _migration_creates_schema(migration_text, schema):
        return f"{migration_path.relative_to(root)} does not create registered schema {schema!r}."
    project_id = config_values.get("project_id")
    if project_id is not None and not isinstance(project_id, str):
        return "supabase/config.toml project_id must be a string."
    if (
        project_ref.strip()
        and isinstance(project_id, str)
        and project_id.strip()
        and project_id.strip() not in {
            str(settings["config_project_id_placeholder"]),
            project_ref.strip(),
        }
    ):
        return "supabase/config.toml project ref conflicts with project environment."
    heading = str(settings["profile_section_heading"])
    for relative in PROFILE_RELATIVE_PATHS:
        path = root / relative
        if not path.is_file():
            return f"Personal Supabase scaffold is missing {relative}."
        text = path.read_text(encoding="utf-8")
        if heading not in text or schema not in text.split(heading, 1)[1]:
            return f"Personal Supabase scaffold profile guidance is incomplete in {relative}."
    env_example = root / ".env.example"
    if not env_example.is_file():
        return "Personal Supabase scaffold is missing .env.example."
    env_text = env_example.read_text(encoding="utf-8")
    schema_key = str(settings["env_schema_key"])
    if f"{schema_key}={schema}" not in env_text:
        return f".env.example does not set {schema_key}={schema}."
    return None


@contextmanager
def temporary_supabase_cli_config(project_root: Path, project_ref: str) -> Iterator[None]:
    """Expose a real project ref to the CLI without persisting it in tracked config."""
    root = project_root.expanduser().resolve()
    config_path = root / "supabase" / "config.toml"
    if not config_path.is_file() or not project_ref.strip():
        yield
        return
    settings = load_personal_supabase_settings()
    placeholder = str(settings["config_project_id_placeholder"])
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project_ref.strip()):
        raise ValueError("Project environment has a malformed Supabase project ref.")
    original = config_path.read_text(encoding="utf-8")
    values = tomllib.loads(original)
    current = values.get("project_id", "")
    if not isinstance(current, str):
        raise ValueError("supabase/config.toml project_id must be a string.")
    if current.strip() and current.strip() not in {placeholder, project_ref.strip()}:
        raise ValueError("supabase/config.toml project ref conflicts with project environment.")
    if current.strip() == project_ref.strip():
        yield
        return
    replacement = f'project_id = "{project_ref.strip()}"'
    if re.search(r"(?m)^\s*project_id\s*=.*$", original):
        prepared = re.sub(r"(?m)^\s*project_id\s*=.*$", replacement, original, count=1)
    else:
        prepared = replacement + "\n\n" + original
    try:
        config_path.write_text(prepared, encoding="utf-8")
        yield
    finally:
        config_path.write_text(original, encoding="utf-8")


def is_personal_supabase_registered(project_root: Path, schema: str | None = None) -> bool:
    """True when the project is marked registered for ``schema`` (or any schema if omitted)."""
    try:
        status = load_personal_supabase_status(project_root)
    except ValueError:
        return False
    if not status.registered:
        return False
    if schema is None:
        return True
    return status.schema == schema


def is_personal_supabase_activated(project_root: Path, schema: str | None = None) -> bool:
    """True when the project is registered and activated for ``schema`` (or any)."""
    try:
        status = load_personal_supabase_status(project_root)
    except ValueError:
        return False
    if not status.registered or not status.activated:
        return False
    if schema is None:
        return True
    return status.schema == schema


def register_personal_supabase(
    project_root: Path,
    schema: str | None = None,
) -> RegistrationResult:
    """Scaffold supabase files, env placeholders, profiles, and a ``.daedalus`` marker.

    Phase 1 only. Remote apply and ecosystem Activate are intentionally out of scope.
    """
    root = project_root.expanduser().resolve()
    settings = load_personal_supabase_settings()
    if schema is None:
        try:
            schema_name = schema_from_project_root(root)
        except ValueError as error:
            return RegistrationResult(
                status="failed",
                schema="",
                message=str(error),
                project_root=root,
            )
    else:
        try:
            schema_name = _validate_schema_name(
                schema,
                int(settings["maximum_schema_name_length"]),
            )
        except ValueError as error:
            return RegistrationResult(
                status="failed",
                schema=str(schema),
                message=str(error),
                project_root=root,
            )

    try:
        status = load_personal_supabase_status(root)
    except ValueError as error:
        return RegistrationResult(
            status="failed",
            schema=schema_name,
            message=str(error),
            project_root=root,
        )

    if status.registered and status.schema == schema_name:
        try:
            _ensure_env_example(root, schema_name, settings)
            # Preserve activation fields on idempotent re-scaffold checks.
            _write_registration_marker(
                root,
                schema_name,
                activated=status.activated,
                last_activate_status=status.last_activate_status,
                last_activate_error=status.last_activate_error,
            )
        except (OSError, ValueError) as error:
            return RegistrationResult(
                status="failed",
                schema=schema_name,
                message=str(error),
                project_root=root,
            )
        return RegistrationResult(
            status="success",
            schema=schema_name,
            message=f"Schema {schema_name!r} is already registered.",
            project_root=root,
            already_registered=True,
        )
    if status.registered and status.schema and status.schema != schema_name:
        return RegistrationResult(
            status="failed",
            schema=schema_name,
            message=(
                f"Project is already registered for schema {status.schema!r}; "
                f"refusing to register {schema_name!r}."
            ),
            project_root=root,
        )

    conflict = _supabase_layout_conflict(root, schema_name, settings)
    if conflict:
        return RegistrationResult(
            status="failed",
            schema=schema_name,
            message=conflict,
            project_root=root,
        )

    try:
        _ensure_supabase_scaffold(root, schema_name, settings)
        _ensure_env_example(root, schema_name, settings)
        _ensure_profile_guidance(root, schema_name, settings)
        _write_registration_marker(root, schema_name, activated=False)
    except (OSError, ValueError) as error:
        return RegistrationResult(
            status="failed",
            schema=schema_name,
            message=str(error),
            project_root=root,
        )

    return RegistrationResult(
        status="success",
        schema=schema_name,
        message=f"Scaffolded personal Supabase schema {schema_name!r}.",
        project_root=root,
    )


def commit_personal_supabase_scaffold(
    project_root: Path,
    operating_branch: str,
    *,
    schema: str | None = None,
    commit_message: str | None = None,
) -> GitScaffoldCommitResult:
    """Require operating-branch HEAD, refuse unrelated dirt, commit scaffold paths only."""
    root = project_root.expanduser().resolve()
    settings = load_personal_supabase_settings()
    branch = operating_branch.strip()
    if not branch:
        return GitScaffoldCommitResult(
            False,
            "Select an operating/target branch before Activate.",
        )
    try:
        status = load_personal_supabase_status(root)
    except ValueError as error:
        return GitScaffoldCommitResult(False, str(error))
    if not status.registered:
        return GitScaffoldCommitResult(False, "Project is not registered for personal Supabase.")
    schema_name = schema or status.schema
    if not schema_name:
        return GitScaffoldCommitResult(False, "Registered project has no schema marker.")
    try:
        schema_name = _validate_schema_name(schema_name, int(settings["maximum_schema_name_length"]))
    except ValueError as error:
        return GitScaffoldCommitResult(False, str(error))

    current = _git_output(["branch", "--show-current"], root)
    if current is None:
        return GitScaffoldCommitResult(False, "Project directory is not a Git repository.")
    if current != branch:
        if not current:
            detail = (
                f"HEAD is detached; check out operating branch {branch!r} before Activate."
            )
        else:
            detail = (
                f"HEAD is on {current!r}; check out operating branch {branch!r} before Activate."
            )
        return GitScaffoldCommitResult(False, detail)

    allowed = set(personal_supabase_scaffold_relative_paths(schema_name, settings))
    dirty = _git_porcelain_paths(root)
    if dirty is None:
        return GitScaffoldCommitResult(False, "Could not read Git status for Activate.")
    # The project-local .env is operator-managed and intentionally remains
    # outside the software-owned commit boundary. It may be untracked in a
    # freshly initialized project, so do not mistake it for unrelated dirt.
    operator_managed = {".env"}
    unrelated = sorted(
        path
        for path in dirty
        if path not in operator_managed and not _path_allowed_for_scaffold(path, allowed)
    )
    if unrelated:
        preview = ", ".join(unrelated[:5])
        suffix = "…" if len(unrelated) > 5 else ""
        return GitScaffoldCommitResult(
            False,
            f"Unrelated dirty files block Activate ({preview}{suffix}). "
            "Commit or clean them, or keep only personal-Supabase scaffold changes.",
        )

    scaffold_dirty = [path for path in dirty if _path_allowed_for_scaffold(path, allowed)]
    message = commit_message or str(settings["activate_commit_message"])
    if not scaffold_dirty:
        return GitScaffoldCommitResult(
            True,
            "Personal Supabase scaffold is already committed on the operating branch.",
            committed=False,
        )

    # Keep deleted tracked paths in the selection so ``git add -A`` records the
    # removal instead of silently omitting it.
    existing = [path for path in allowed if (root / path).exists() or path in scaffold_dirty]
    return _commit_paths(root, existing, message)


def _commit_paths(
    directory: Path,
    paths: tuple[str, ...] | list[str],
    message: str,
) -> GitScaffoldCommitResult:
    selected = list(dict.fromkeys(path.replace("\\", "/") for path in paths))
    if not selected:
        return GitScaffoldCommitResult(True, "Nothing to commit.", committed=False)
    # A narrow ``add`` followed by an ordinary commit can include stale index
    # entries. ``--only`` makes the commit boundary explicit and keeps an
    # unrelated pre-staged file out of the software-owned commit.
    for attempt in range(2):
        add = _run_git(["add", "-A", "--", *selected], directory)
        if not add.succeeded:
            return GitScaffoldCommitResult(False, add.message or "Failed to stage paths.")
        staged = _git_output(["diff", "--cached", "--name-only", "--", *selected], directory)
        if staged is None:
            return GitScaffoldCommitResult(False, "Could not inspect staged Activate changes.")
        if not staged.strip():
            return GitScaffoldCommitResult(True, "Nothing to commit.", committed=False)
        commit = _run_git(["commit", "--only", "-m", message, "--", *selected], directory)
        if not commit.succeeded:
            return GitScaffoldCommitResult(False, commit.message or "Failed to commit paths.")
        remaining = _git_porcelain_paths(directory)
        if remaining is None:
            return GitScaffoldCommitResult(
                False,
                "Commit completed, but Activate could not verify the worktree state.",
                committed=True,
            )
        changed_again = sorted(path for path in remaining if path in selected)
        if not changed_again:
            return GitScaffoldCommitResult(True, "Committed personal Supabase changes.", committed=True)
        if attempt == 0:
            continue
        preview = ", ".join(changed_again[:5])
        suffix = "…" if len(changed_again) > 5 else ""
        return GitScaffoldCommitResult(
            False,
            f"Files changed while Activate was committing ({preview}{suffix}); retry Activate.",
            committed=True,
        )
    return GitScaffoldCommitResult(False, "Failed to commit paths.")


def preflight_personal_supabase(
    project_root: Path,
    *,
    executable: str = "supabase",
    timeout_seconds: float | None = None,
    run_process=subprocess.run,
    find_executable=shutil.which,
) -> PreflightResult:
    """Run access-method-aware live connectivity checks; never mutates schema."""
    settings = load_personal_supabase_settings()
    timeout = float(
        timeout_seconds
        if timeout_seconds is not None
        else settings["preflight_timeout_seconds"]
    )
    values = load_project_personal_supabase_env_values(project_root)
    resolved, resolve_error = resolve_personal_supabase_environment(
        values,
        settings,
        require_database_access=True,
    )
    if resolve_error or resolved is None:
        return PreflightResult(False, resolve_error or "Project environment could not be resolved.")
    project_ref = resolved[str(settings["env_project_ref_key"])]
    access_token = resolved.get(str(settings["env_access_token_key"]), "").strip()
    db_url = resolved.get(str(settings["env_db_url_key"]), "").strip()
    if find_executable(executable) is None:
        return PreflightResult(False, f"{executable} is not available on PATH.")

    env = {**os.environ, **values, **resolved}
    if access_token:
        try:
            process = run_process(
                [executable, "projects", "list"],
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return PreflightResult(False, "Supabase projects list timed out.", method="access_token")
        except OSError as error:
            return PreflightResult(False, str(error), method="access_token")
        output = "\n".join(
            part.strip() for part in (process.stdout, process.stderr) if part and part.strip()
        )
        if process.returncode != 0:
            redacted = redact_environment_values(output, env) or "Supabase projects list failed."
            return PreflightResult(False, redacted, method="access_token")
        if project_ref not in output:
            return PreflightResult(
                False,
                f"Supabase project ref {project_ref!r} was not visible to the access token.",
                method="access_token",
            )
        return PreflightResult(True, "Supabase access-token preflight succeeded.", method="access_token")

    probe = _probe_database_url(
        db_url,
        timeout,
        project_ref=project_ref,
        find_executable=find_executable,
        run_process=run_process,
        direct_dns_hint=str(settings.get("direct_database_dns_hint", "")),
    )
    if not probe.succeeded:
        return PreflightResult(False, probe.message, method="db_url")
    return PreflightResult(True, probe.message or "Supabase DB URL preflight succeeded.", method="db_url")


def activate_personal_supabase(
    project_root: Path,
    operating_branch: str,
    *,
    schema: str | None = None,
    executable: str = "supabase",
    run_process=subprocess.run,
    find_executable=shutil.which,
    progress_callback: Callable[[str], None] | None = None,
) -> ActivationResult:
    """Phase 1 (if needed) then Phase 2: Git commit, preflight, and migration push.

    ``progress_callback`` receives short, credential-free phase labels for a
    caller-owned progress surface.
    """
    root = project_root.expanduser().resolve()
    settings = load_personal_supabase_settings()

    def report_progress(message: str) -> None:
        """Report UI progress without letting a stale UI callback break activation."""
        if progress_callback is None:
            return
        try:
            progress_callback(message)
        except Exception:
            # Activation owns the durable operation; the progress surface is
            # best-effort because it can disappear during application shutdown.
            pass

    report_progress("Checking registration")
    try:
        status = load_personal_supabase_status(root)
    except ValueError as error:
        return ActivationResult("failed", schema or "", str(error), root)

    if schema is None:
        try:
            schema_name = status.schema or schema_from_project_root(root)
        except ValueError as error:
            return ActivationResult("failed", "", str(error), root)
    else:
        try:
            schema_name = _validate_schema_name(schema, int(settings["maximum_schema_name_length"]))
        except ValueError as error:
            return ActivationResult("failed", str(schema), str(error), root)

    if status.registered and status.activated and status.schema == schema_name:
        report_progress("Already activated")
        return ActivationResult(
            "success",
            schema_name,
            f"Schema {schema_name!r} is already activated.",
            root,
            activated=True,
        )

    scaffolded = False
    if not status.registered:
        report_progress("Scaffolding project files")
        registration = register_personal_supabase(root, schema=schema_name)
        if registration.status != "success":
            return ActivationResult("failed", schema_name, registration.message, root)
        scaffolded = not registration.already_registered
        status = load_personal_supabase_status(root)
    elif status.schema != schema_name:
        return ActivationResult(
            "failed",
            schema_name,
            (
                f"Project is already registered for schema {status.schema!r}; "
                f"refusing to activate {schema_name!r}."
            ),
            root,
        )
    else:
        report_progress("Using existing scaffold")

    report_progress("Validating scaffold")
    scaffold_error = _validate_supabase_scaffold(root, schema_name, settings)
    if scaffold_error:
        _write_registration_marker(
            root,
            schema_name,
            activated=False,
            last_activate_status=ACTIVATE_STATUS_BLOCKED_SCAFFOLD,
            last_activate_error=_short_error(scaffold_error),
        )
        return ActivationResult(
            "blocked",
            schema_name,
            scaffold_error,
            root,
            scaffolded=scaffolded,
            blocked_reason=ACTIVATE_STATUS_BLOCKED_SCAFFOLD,
        )

    report_progress("Committing scaffold changes")
    git_result = commit_personal_supabase_scaffold(
        root,
        operating_branch,
        schema=schema_name,
        commit_message=str(settings["activate_commit_message"]),
    )
    if not git_result.succeeded:
        _write_registration_marker(
            root,
            schema_name,
            activated=False,
            last_activate_status=ACTIVATE_STATUS_BLOCKED_GIT,
            last_activate_error=_short_error(git_result.message),
        )
        return ActivationResult(
            "blocked",
            schema_name,
            git_result.message,
            root,
            scaffolded=scaffolded,
            committed=False,
            blocked_reason=ACTIVATE_STATUS_BLOCKED_GIT,
        )

    report_progress("Validating environment")
    prepared = bootstrap_personal_supabase(root, require_database_access=True)
    if prepared.status != "success":
        message = prepared.message or "Project environment validation failed."
        _write_registration_marker(
            root,
            schema_name,
            activated=False,
            last_activate_status=ACTIVATE_STATUS_BLOCKED_SUPABASE,
            last_activate_error=_short_error(message),
        )
        return ActivationResult(
            "blocked",
            schema_name,
            message,
            root,
            scaffolded=scaffolded,
            committed=git_result.committed,
            blocked_reason=ACTIVATE_STATUS_BLOCKED_SUPABASE,
        )

    report_progress("Checking Supabase connection")
    preflight = preflight_personal_supabase(
        root,
        executable=executable,
        run_process=run_process,
        find_executable=find_executable,
    )
    if not preflight.succeeded:
        message = preflight.message or "Supabase connectivity preflight failed."
        _write_registration_marker(
            root,
            schema_name,
            activated=False,
            last_activate_status=ACTIVATE_STATUS_BLOCKED_SUPABASE,
            last_activate_error=_short_error(message),
        )
        return ActivationResult(
            "blocked",
            schema_name,
            message,
            root,
            scaffolded=scaffolded,
            committed=git_result.committed,
            blocked_reason=ACTIVATE_STATUS_BLOCKED_SUPABASE,
        )

    environment = prepared.environment or {}
    project_ref = (prepared.project_ref or "").strip()
    report_progress("Pushing migrations")
    try:
        with temporary_supabase_cli_config(root, project_ref):
            pushed = push_migrations(root, executable=executable, env=environment)
    except ValueError as error:
        message = str(error)
        _write_registration_marker(
            root,
            schema_name,
            activated=False,
            last_activate_status=ACTIVATE_STATUS_BLOCKED_SUPABASE,
            last_activate_error=_short_error(message),
        )
        return ActivationResult(
            "blocked",
            schema_name,
            message,
            root,
            scaffolded=scaffolded,
            committed=git_result.committed,
            blocked_reason=ACTIVATE_STATUS_BLOCKED_SUPABASE,
        )

    if not pushed.succeeded:
        message = (
            redact_environment_values(pushed.output, environment)
            or "Supabase migration push failed."
        )
        _write_registration_marker(
            root,
            schema_name,
            activated=False,
            last_activate_status=ACTIVATE_STATUS_BLOCKED_SUPABASE,
            last_activate_error=_short_error(message),
        )
        return ActivationResult(
            "blocked",
            schema_name,
            message,
            root,
            scaffolded=scaffolded,
            committed=git_result.committed,
            blocked_reason=ACTIVATE_STATUS_BLOCKED_SUPABASE,
        )

    _write_registration_marker(
        root,
        schema_name,
        activated=True,
        last_activate_status=ACTIVATE_STATUS_SUCCESS,
        last_activate_error=None,
    )
    status_commit = _commit_paths(
        root,
        (DAEDALUS_CONFIG_FILENAME,),
        str(settings.get("activate_status_commit_message", "Mark personal Supabase schema activated.")),
    )
    if not status_commit.succeeded:
        return ActivationResult(
            "success",
            schema_name,
            (
                f"Activated personal Supabase schema {schema_name!r}, "
                f"but activation marker commit failed: {status_commit.message}"
            ),
            root,
            activated=True,
            scaffolded=scaffolded,
            committed=git_result.committed,
        )
    report_progress("Complete")
    return ActivationResult(
        "success",
        schema_name,
        f"Activated personal Supabase schema {schema_name!r}.",
        root,
        activated=True,
        scaffolded=scaffolded,
        committed=git_result.committed or status_commit.committed,
    )


def profile_guidance_section(schema: str, settings: dict | None = None) -> str:
    """Return the markdown section appended to coding/architecture profiles."""
    values = settings or load_personal_supabase_settings()
    heading = str(values["profile_section_heading"])
    env_key = str(values["env_schema_key"])
    return (
        f"{heading}\n\n"
        f"This project uses a dedicated Postgres schema `{schema}` on the operator's "
        "shared personal Supabase database. Do **not** use the default `public` schema "
        "for application tables or migrations.\n\n"
        f"- Schema name is `{schema}` (see `{env_key}` in `.env.example` and the "
        "`[personal_supabase]` marker in `.daedalus`).\n"
        "- This project's ignored `.env` is the canonical source for "
        "`SUPABASE_URL`, publishable/secret API keys (legacy anon/service_role aliases "
        "still work), and one database access setting (`SUPABASE_DB_URL` or "
        "`SUPABASE_ACCESS_TOKEN`); the project ref is optional when the URL is "
        "`https://<ref>.supabase.co`. Operators set those values manually; Daedalus "
        "never writes credentials into project `.env` files.\n"
        f"- Qualify SQL, migrations, RLS policies, and client/API configuration for `{schema}`.\n"
        "- Never assume PostgREST or Supabase clients default to `public` for this app.\n"
        "- Auth is shared across apps on this Supabase project; reuse the existing auth setup.\n"
        "- Agents must not run `supabase db push`; orchestration owns remote migration apply "
        "after verification when `supabase/migrations/` changes, and Activate owns the first apply.\n"
        "- File scaffolding alone is not ecosystem-ready; the operator must Activate via Daedalus "
        "(from the Ctrl+K Command Menu) so the software layer commits the scaffold and pushes migrations.\n"
        "- After the first remote apply, the operator must allow-list this schema in the "
        "Supabase Dashboard Data API / PostgREST exposed-schemas settings.\n"
    )


def _short_error(message: str, limit: int = 240) -> str:
    text = " ".join(message.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _path_allowed_for_scaffold(path: str, allowed: set[str]) -> bool:
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.rstrip("/")
    if normalized in allowed:
        return True
    if any(candidate.startswith(normalized + "/") for candidate in allowed):
        # Allow parent directory entries such as ``supabase/`` while scaffolding.
        return True
    return False


def _git_output(command: list[str], directory: Path) -> str | None:
    try:
        process = subprocess.run(
            ["git", *command],
            cwd=directory,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if process.returncode != 0:
        return None
    return process.stdout.strip()


@dataclass(frozen=True)
class _GitCommandResult:
    succeeded: bool
    message: str = ""


def _run_git(command: list[str], directory: Path) -> _GitCommandResult:
    try:
        process = subprocess.run(
            ["git", *command],
            cwd=directory,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return _GitCommandResult(False, str(error))
    if process.returncode != 0:
        output = "\n".join(
            part.strip() for part in (process.stdout, process.stderr) if part and part.strip()
        )
        return _GitCommandResult(False, output or f"git {' '.join(command)} failed.")
    return _GitCommandResult(True)


def _git_porcelain_paths(directory: Path) -> set[str] | None:
    try:
        process = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=directory,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if process.returncode != 0:
        return None
    paths: set[str] = set()
    for line in process.stdout.splitlines():
        if len(line) < 4:
            continue
        entry = line[3:]
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        entry = entry.strip().strip('"')
        if entry:
            paths.add(entry.replace("\\", "/"))
    return paths


def _probe_database_url(
    db_url: str,
    timeout: float,
    *,
    project_ref: str,
    find_executable,
    run_process,
    direct_dns_hint: str = "",
) -> PreflightResult:
    parsed = urlparse(db_url)
    host = parsed.hostname
    if not host:
        return PreflightResult(False, "SUPABASE_DB_URL is missing a host.")
    direct_host_ref = _direct_database_host_project_ref(host)
    if direct_host_ref and direct_host_ref != project_ref.lower():
        return PreflightResult(
            False,
            "SUPABASE_DB_URL points to database project "
            f"{direct_host_ref!r}, but SUPABASE_URL points to {project_ref!r}. "
            "Use the database connection string for the same Supabase project.",
        )
    port = parsed.port or 5432
    if find_executable("psql") is not None:
        try:
            process = run_process(
                ["psql", db_url, "-v", "ON_ERROR_STOP=1", "-c", "SELECT 1;"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return PreflightResult(False, "Database reachability check timed out.")
        except OSError as error:
            return PreflightResult(False, str(error))
        if process.returncode == 0:
            return PreflightResult(True, "Database reachability check succeeded.")
        output = "\n".join(
            part.strip() for part in (process.stdout, process.stderr) if part and part.strip()
        )
        return PreflightResult(False, output or "Database reachability check failed.")

    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except socket.gaierror as error:
        direct_hint = (
            f" {direct_dns_hint.format(host=host, port=port, project_ref=project_ref)}"
            if direct_dns_hint and direct_host_ref
            else ""
        )
        return PreflightResult(
            False,
            f"DNS could not resolve database host {host}:{port} ({error}). "
            "Check SUPABASE_DB_URL against the project's Connect settings; if the host "
            "matches, check this machine's DNS/network."
            f"{direct_hint} Supabase CLI login does not affect DNS resolution.",
        )
    except OSError as error:
        return PreflightResult(False, f"Could not reach database host {host}:{port} ({error}).")
    return PreflightResult(True, f"Database host {host}:{port} is reachable.")


def _direct_database_host_project_ref(host: str) -> str | None:
    """Return the project ref from a canonical Supabase direct DB hostname."""
    prefix = "db."
    suffix = ".supabase.co"
    normalized = host.lower()
    if not normalized.startswith(prefix) or not normalized.endswith(suffix):
        return None
    project_ref = normalized[len(prefix) : -len(suffix)]
    return project_ref or None


def _supabase_layout_conflict(root: Path, schema: str, settings: dict) -> str | None:
    supabase = root / "supabase"
    if not supabase.exists():
        return None
    if not supabase.is_dir():
        return "A file named supabase exists; refusing to scaffold a directory."

    migrations = supabase / "migrations"
    if migrations.exists() and not migrations.is_dir():
        return "supabase/migrations exists but is not a directory."

    expected_name = str(settings["migration_filename"])
    if migrations.is_dir():
        foreign = []
        for path in sorted(migrations.glob("*.sql")):
            text = path.read_text(encoding="utf-8")
            owns_schema = _migration_creates_schema(text, schema)
            if path.name == expected_name and owns_schema:
                continue
            if owns_schema and path.name != expected_name:
                # Alternate filename still claiming this schema is acceptable.
                continue
            foreign.append(path.name)
        if foreign:
            return (
                "Existing supabase/migrations content is incompatible with personal "
                f"schema registration ({', '.join(foreign)})."
            )
    return None


def _migration_creates_schema(text: str, schema: str) -> bool:
    pattern = re.compile(
        rf'CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+"{re.escape(schema)}"\s*;',
        re.IGNORECASE,
    )
    return bool(pattern.search(text))


def _ensure_supabase_scaffold(root: Path, schema: str, settings: dict) -> None:
    supabase = root / "supabase"
    migrations = supabase / "migrations"
    migrations.mkdir(parents=True, exist_ok=True)

    config_path = supabase / "config.toml"
    if not config_path.exists():
        placeholder = str(settings["config_project_id_placeholder"])
        config_path.write_text(
            (
                "# Scaffolded by Daedalus personal Supabase registration.\n"
                "# Daedalus supplies the project ref temporarily at Activate/push "
                "(from SUPABASE_PROJECT_REF or derived from SUPABASE_URL).\n"
                "# Phase 1 writes files only; Activate / orchestration owns `supabase db push`.\n"
                f'project_id = "{placeholder}"\n'
                "\n"
                "[api]\n"
                "# Exposed schemas for a shared project are allow-listed in the Supabase\n"
                "# Dashboard (Data API / PostgREST). Manually add this project's schema\n"
                "# after the CREATE SCHEMA migration is applied remotely.\n"
            ),
            encoding="utf-8",
        )

    migration_path = migrations / str(settings["migration_filename"])
    if not migration_path.exists():
        migration_path.write_text(
            (
                f"-- Personal shared Supabase schema for this Daedalus project.\n"
                f"-- Operators must allow-list \"{schema}\" in Supabase Data API settings.\n"
                f'CREATE SCHEMA IF NOT EXISTS "{schema}";\n'
                "\n"
                f'GRANT USAGE ON SCHEMA "{schema}" TO anon, authenticated, service_role;\n'
                f'GRANT ALL ON SCHEMA "{schema}" TO postgres, service_role;\n'
                f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" '
                "GRANT ALL ON TABLES TO postgres, service_role;\n"
                f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" '
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO anon, authenticated;\n"
            ),
            encoding="utf-8",
        )
    elif not _migration_creates_schema(migration_path.read_text(encoding="utf-8"), schema):
        raise ValueError(
            f"{migration_path.name} exists but does not create schema {schema!r}."
        )


def _ensure_env_example(root: Path, schema: str, settings: dict) -> None:
    path = root / ".env.example"
    block = _env_example_block(schema, settings)
    if not path.exists():
        path.write_text(block, encoding="utf-8")
        return

    existing = path.read_text(encoding="utf-8")
    schema_key = str(settings["env_schema_key"])
    match = re.search(rf"(?m)^{re.escape(schema_key)}=(.*)$", existing)
    if match:
        current = match.group(1).strip()
        if current and current != schema:
            raise ValueError(
                f".env.example already sets {schema_key}={current!r}; "
                f"refusing to overwrite with {schema!r}."
            )
        canonical_keys = tuple(str(key) for key in settings["canonical_env_keys"])
        if (
            current == schema
            and "allow-list" in existing.lower()
            and all(re.search(rf"(?m)^{re.escape(key)}=", existing) for key in canonical_keys)
        ):
            return
        # Keep other keys; refresh the schema line / ensure guidance when missing.
        updated = re.sub(
            rf"(?m)^{re.escape(schema_key)}=.*$",
            f"{schema_key}={schema}",
            existing,
            count=1,
        )
        missing_keys = [
            key for key in canonical_keys
            if not re.search(rf"(?m)^{re.escape(key)}=", updated)
        ]
        if missing_keys:
            updated = updated.rstrip() + "\n\n" + _shared_env_example_block(settings, missing_keys)
        if "allow-list" not in updated.lower():
            updated = updated.rstrip() + "\n\n" + _allow_list_comment(schema) + "\n"
        path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")
        return

    path.write_text(existing.rstrip() + "\n\n" + block, encoding="utf-8")


def _env_example_block(schema: str, settings: dict) -> str:
    return (
        _shared_env_example_block(settings)
        + "\n"
        "# Project-specific Postgres schema on the shared database (never use public).\n"
        f"{settings['env_schema_key']}={schema}\n"
        "\n"
        f"{_allow_list_comment(schema)}\n"
    )


def _shared_env_example_block(settings: dict, keys: list[str] | None = None) -> str:
    selected = tuple(keys or (str(key) for key in settings["canonical_env_keys"]))
    lines = [
        "# Shared personal Supabase project. Values are owned by this project's ignored `.env`.",
        "# Prefer SUPABASE_PUBLISHABLE_KEY + SUPABASE_SECRET_KEY (anon/service_role and",
        "# SUPABASE_PRIVATE_KEY remain accepted aliases). Project ref is optional when",
        "# SUPABASE_URL is https://<project-ref>.supabase.co.",
        "# Do not put real credentials here; set them in this project's ignored `.env`.",
    ]
    database_keys = {
        str(settings["env_db_url_key"]),
        str(settings["env_access_token_key"]),
    }
    project_ref_key = str(settings["env_project_ref_key"])
    for key in selected:
        if key == project_ref_key:
            lines.append("# Optional when SUPABASE_URL is https://<project-ref>.supabase.co:")
        if key in database_keys and not any(line.startswith("# Database access") for line in lines):
            lines.append(
                "# Database access for Activate / migration push (set at least one in this project's `.env`):"
            )
        lines.append(f"{key}=")
    return "\n".join(lines) + "\n"


def _allow_list_comment(schema: str) -> str:
    return (
        f"# After migrations apply, allow-list schema \"{schema}\" in Supabase Dashboard → "
        "Project Settings → Data API (PostgREST exposed schemas)."
    )


def _ensure_profile_guidance(root: Path, schema: str, settings: dict) -> None:
    section = profile_guidance_section(schema, settings)
    heading = str(settings["profile_section_heading"])
    for relative in PROFILE_RELATIVE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if heading in text:
                if schema not in text.split(heading, 1)[1]:
                    raise ValueError(
                        f"{relative} already has a Personal Supabase Schema section "
                        f"that does not reference {schema!r}."
                    )
                continue
            path.write_text(text.rstrip() + "\n\n" + section, encoding="utf-8")
        else:
            path.write_text(section, encoding="utf-8")


def _write_registration_marker(
    root: Path,
    schema: str,
    *,
    activated: bool = False,
    last_activate_status: str | None = None,
    last_activate_error: str | None = None,
) -> None:
    path = root / DAEDALUS_CONFIG_FILENAME
    lines = [
        f"[{SECTION_TABLE}]",
        "registered = true",
        f'schema = "{schema}"',
        f"activated = {'true' if activated else 'false'}",
    ]
    if last_activate_status:
        lines.append(f'last_activate_status = "{_toml_escape(last_activate_status)}"')
    if last_activate_error:
        lines.append(f'last_activate_error = "{_toml_escape(last_activate_error)}"')
    section = "\n".join(lines) + "\n"
    if not path.exists():
        path.write_text(section, encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(?ms)^\[{re.escape(SECTION_TABLE)}\]\n.*?(?=^\[|\Z)",
    )
    if pattern.search(text):
        updated = pattern.sub(section + "\n", text, count=1)
    else:
        updated = text.rstrip() + "\n\n" + section
    path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
