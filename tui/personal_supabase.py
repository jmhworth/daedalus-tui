"""File-only personal shared-Supabase schema registration for target projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
from pathlib import Path
import re
import tomllib
from typing import Iterator

from .environment import read_env_file, synchronize_env_file
from .project_config import DAEDALUS_CONFIG_FILENAME

TUI_ROOT = Path(__file__).resolve().parents[1]
PARAMETER_PATH = TUI_ROOT / "parameter_files" / "daedalus-tui-personal-supabase.toml"
PROFILE_RELATIVE_PATHS = (
    Path(".agents") / "profiles" / "coding.md",
    Path(".agents") / "profiles" / "architecture.md",
)
SECTION_TABLE = "personal_supabase"


def _validate_schema_name(schema: object, maximum_length: int) -> str:
    # Imported lazily to avoid a circular import with project_initializer.
    from .project_initializer import validate_project_name

    return validate_project_name(schema, maximum_length)


@dataclass(frozen=True)
class PersonalSupabaseStatus:
    """Registration marker loaded from a target project's ``.daedalus`` file."""

    registered: bool
    schema: str | None = None


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
    return PersonalSupabaseStatus(registered=registered, schema=schema.strip() if isinstance(schema, str) else None)


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


def register_personal_supabase(
    project_root: Path,
    schema: str | None = None,
) -> RegistrationResult:
    """Scaffold supabase files, env placeholders, profiles, and a ``.daedalus`` marker.

    Remote apply is intentionally out of scope; orchestration owns ``supabase db push``.
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
        _write_registration_marker(root, schema_name)
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
        message=f"Registered personal Supabase schema {schema_name!r}.",
        project_root=root,
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
        "after verification when `supabase/migrations/` changes.\n"
        "- After the first remote apply, the operator must allow-list this schema in the "
        "Supabase Dashboard Data API / PostgREST exposed-schemas settings.\n"
    )


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
                "# Registration writes files only; orchestration owns `supabase db push`.\n"
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


def _write_registration_marker(root: Path, schema: str) -> None:
    path = root / DAEDALUS_CONFIG_FILENAME
    section = (
        f"[{SECTION_TABLE}]\n"
        "registered = true\n"
        f'schema = "{schema}"\n'
    )
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
