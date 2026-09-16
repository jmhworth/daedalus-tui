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
import tomllib
from collections.abc import Callable, Iterator

from .environment import read_env_file, redact_environment_values, synchronize_env_file
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


def personal_supabase_environment_settings(settings: dict | None = None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return canonical and required environment keys from the feature parameters."""
    values = settings or load_personal_supabase_settings()
    canonical = tuple(str(key) for key in values["canonical_env_keys"])
    required = tuple(str(key) for key in values["required_env_keys"])
    return canonical, required


def load_personal_supabase_settings() -> dict:
    """Load tunables for schema registration from the paired parameter file."""
    with PARAMETER_PATH.open("rb") as source:
        return tomllib.load(source)


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


def bootstrap_personal_supabase(
    project_root: Path,
    launch_root: Path,
    *,
    require_database_access: bool = True,
) -> PersonalSupabaseBootstrapResult:
    """Validate registration and synchronize the launch-root shared environment.

    This helper performs no remote operation. It only prepares ignored local
    files and validates that the tracked Supabase scaffold can be used by the
    orchestration-owned CLI push.
    """
    root = project_root.expanduser().resolve()
    source = launch_root.expanduser().resolve() / ".env"
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

    canonical, required = personal_supabase_environment_settings(settings)
    source_values = read_env_file(source)
    project_ref = source_values.get(str(settings["env_project_ref_key"]), "").strip()
    if project_ref and not re.fullmatch(r"[A-Za-z0-9_-]+", project_ref):
        return PersonalSupabaseBootstrapResult(
            "failed",
            root,
            schema=schema,
            message="Launch environment has a malformed Supabase project ref.",
            environment=source_values,
        )
    access_keys = (str(settings["env_db_url_key"]), str(settings["env_access_token_key"]))
    if require_database_access and not any(source_values.get(key, "").strip() for key in access_keys):
        return PersonalSupabaseBootstrapResult(
            "failed",
            root,
            schema=schema,
            message=(
                "Launch environment must define one database access setting: "
                + " or ".join(access_keys)
                + "."
            ),
            environment=source_values,
        )
    scaffold_error = _validate_supabase_scaffold(root, schema, settings, project_ref)
    if scaffold_error:
        return PersonalSupabaseBootstrapResult("failed", root, schema=schema, message=scaffold_error)
    sync = synchronize_env_file(
        source,
        root / ".env",
        canonical,
        project_values={str(settings["env_schema_key"]): schema},
        required_keys=required,
    )
    if not sync.succeeded:
        return PersonalSupabaseBootstrapResult(
            "failed", root, schema=schema, message=sync.message, environment=sync.values
        )
    return PersonalSupabaseBootstrapResult(
        "success",
        root,
        schema=schema,
        project_ref=project_ref,
        message="Supabase environment synchronized.",
        environment=sync.values,
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
        return "supabase/config.toml project ref conflicts with launch environment."
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
        raise ValueError("Launch environment has a malformed Supabase project ref.")
    original = config_path.read_text(encoding="utf-8")
    values = tomllib.loads(original)
    current = values.get("project_id", "")
    if not isinstance(current, str):
        raise ValueError("supabase/config.toml project_id must be a string.")
    if current.strip() and current.strip() not in {placeholder, project_ref.strip()}:
        raise ValueError("supabase/config.toml project ref conflicts with launch environment.")
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
    unrelated = sorted(path for path in dirty if not _path_allowed_for_scaffold(path, allowed))
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

    existing = [path for path in allowed if (root / path).exists() or path in scaffold_dirty]
    return _commit_paths(root, existing, message)


def _commit_paths(
    directory: Path,
    paths: tuple[str, ...] | list[str],
    message: str,
) -> GitScaffoldCommitResult:
    selected = [path for path in paths if (directory / path).exists()]
    if not selected:
        return GitScaffoldCommitResult(True, "Nothing to commit.", committed=False)
    add = _run_git(["add", "--", *selected], directory)
    if not add.succeeded:
        return GitScaffoldCommitResult(False, add.message or "Failed to stage paths.")
    staged = _git_output(["diff", "--cached", "--name-only"], directory)
    if staged is None:
        return GitScaffoldCommitResult(False, "Could not inspect staged Activate changes.")
    if not staged.strip():
        return GitScaffoldCommitResult(True, "Nothing to commit.", committed=False)
    commit = _run_git(["commit", "-m", message], directory)
    if not commit.succeeded:
        return GitScaffoldCommitResult(False, commit.message or "Failed to commit paths.")
    return GitScaffoldCommitResult(True, "Committed personal Supabase changes.", committed=True)


def preflight_personal_supabase(
    launch_root: Path,
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
    source = launch_root.expanduser().resolve() / ".env"
    values = read_env_file(source)
    _, required = personal_supabase_environment_settings(settings)
    missing = [key for key in required if not values.get(key, "").strip()]
    if missing:
        return PreflightResult(False, f"Launch environment missing required keys: {', '.join(missing)}.")
    project_ref = values.get(str(settings["env_project_ref_key"]), "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project_ref):
        return PreflightResult(False, "Launch environment has a malformed Supabase project ref.")
    access_token = values.get(str(settings["env_access_token_key"]), "").strip()
    db_url = values.get(str(settings["env_db_url_key"]), "").strip()
    if not access_token and not db_url:
        return PreflightResult(
            False,
            "Launch environment must define SUPABASE_ACCESS_TOKEN or SUPABASE_DB_URL.",
        )
    if find_executable(executable) is None:
        return PreflightResult(False, f"{executable} is not available on PATH.")

    env = {**os.environ, **values}
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
            redacted = redact_environment_values(output, values) or "Supabase projects list failed."
            return PreflightResult(False, redacted, method="access_token")
        if project_ref not in output:
            return PreflightResult(
                False,
                f"Supabase project ref {project_ref!r} was not visible to the access token.",
                method="access_token",
            )
        return PreflightResult(True, "Supabase access-token preflight succeeded.", method="access_token")

    probe = _probe_database_url(db_url, timeout, find_executable=find_executable, run_process=run_process)
    if not probe.succeeded:
        return PreflightResult(False, probe.message, method="db_url")
    return PreflightResult(True, probe.message or "Supabase DB URL preflight succeeded.", method="db_url")


def activate_personal_supabase(
    project_root: Path,
    launch_root: Path,
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
    launch = launch_root.expanduser().resolve()
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

    report_progress("Synchronizing environment")
    prepared = bootstrap_personal_supabase(root, launch, require_database_access=True)
    if prepared.status != "success":
        message = prepared.message or "Environment synchronization failed."
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
        launch,
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
        f"- Read the schema name from `{env_key}` in the project `.env` (expected value: `{schema}`).\n"
        "- The launch-root `.env` is the canonical shared source for the project ref, URL, keys, "
        "and database access settings; Daedalus synchronizes the ignored project `.env` at launch.\n"
        f"- Qualify SQL, migrations, RLS policies, and client/API configuration for `{schema}`.\n"
        "- Never assume PostgREST or Supabase clients default to `public` for this app.\n"
        "- Auth is shared across apps on this Supabase project; reuse the existing auth setup.\n"
        "- Agents must not run `supabase db push`; orchestration owns remote migration apply "
        "after verification when `supabase/migrations/` changes, and Activate owns the first apply.\n"
        "- File scaffolding alone is not ecosystem-ready; the operator must Activate via Daedalus "
        "(`Option+4`) so the software layer commits the scaffold and pushes migrations.\n"
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
    find_executable,
    run_process,
) -> PreflightResult:
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

    parsed = urlparse(db_url)
    host = parsed.hostname
    if not host:
        return PreflightResult(False, "SUPABASE_DB_URL is missing a host.")
    port = parsed.port or 5432
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as error:
        return PreflightResult(False, f"Could not reach database host {host}:{port} ({error}).")
    return PreflightResult(True, f"Database host {host}:{port} is reachable.")


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
                "# Daedalus supplies the launch-root SUPABASE_PROJECT_REF temporarily at launch.\n"
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
        "# Shared personal Supabase project. Values are owned by the Daedalus launch-root `.env`.",
        "# Do not add credentials here; Daedalus synchronizes this ignored file at launch.",
    ]
    database_keys = {
        str(settings["env_db_url_key"]),
        str(settings["env_access_token_key"]),
    }
    for key in selected:
        if key in database_keys and not any(line.startswith("# Database access") for line in lines):
            lines.append("# Database access (set at least one in the launch-root `.env`):")
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
