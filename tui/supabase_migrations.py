"""Orchestration-owned Supabase migration push for target project worktrees."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import re
import tomllib
from threading import Lock


TUI_ROOT = Path(__file__).resolve().parents[1]
PARAMETER_PATH = TUI_ROOT / "parameter_files" / "daedalus-tui-personal-supabase.toml"
ROOT_MIGRATION_LOCK = Lock()


def _migration_directory_name() -> str:
    with PARAMETER_PATH.open("rb") as source:
        return str(tomllib.load(source)["migration_directory"])


MIGRATIONS_PATH = "supabase/migrations/"


@dataclass(frozen=True)
class PushResult:
    succeeded: bool
    output: str = ""


@dataclass(frozen=True)
class MigrationSyncResult:
    succeeded: bool
    copied: tuple[str, ...] = ()
    conflicts: tuple[tuple[str, str, str], ...] = ()
    output: str = ""


def migrations_pending(worktree: Path, base_commit: str) -> bool:
    """Return True when project migration SQL changed from the task base."""
    personal_path = _migration_directory_name()
    try:
        changed = subprocess.run(
            ["git", "diff", "--name-only", base_commit, "--", personal_path, MIGRATIONS_PATH],
            cwd=worktree,
            capture_output=True,
            text=True,
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", personal_path, MIGRATIONS_PATH],
            cwd=worktree,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if changed.returncode != 0 or untracked.returncode != 0:
        return False
    return bool(changed.stdout.strip() or untracked.stdout.strip())


def synchronize_personal_migrations(project: Path) -> MigrationSyncResult:
    """Copy project migrations into the TUI aggregate, preserving root authority."""
    project_root = project.expanduser().resolve()
    relative = Path(_migration_directory_name())
    source_dir = project_root / relative
    destination_dir = TUI_ROOT / "supabase" / "migrations"
    if not source_dir.is_dir():
        return MigrationSyncResult(False, output=f"Missing project migration directory: {relative}/.")
    try:
        marker_path = project_root / ".daedalus"
        marker = tomllib.loads(marker_path.read_text(encoding="utf-8"))
        schema = str(marker.get("personal_supabase", {}).get("schema", ""))
        if not schema:
            return MigrationSyncResult(False, output="Registered project has no personal Supabase schema marker.")
        destination_dir.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        conflicts: list[tuple[str, str, str]] = []
        for source in sorted(source_dir.glob("*.sql")):
            # Match the known schema as a literal prefix. Splitting on underscores
            # is ambiguous because both schema names and descriptions may contain them.
            expected_name = re.compile(
                rf"\d{{12}}_{re.escape(schema)}_[A-Za-z0-9_-]+\.sql"
            )
            if expected_name.fullmatch(source.name) is None:
                return MigrationSyncResult(
                    False,
                    output=(
                        f"Invalid migration filename {source.name!r}; expected "
                        f"<YYYYMMDDHHMM>_{schema}_<description>.sql."
                    ),
                )
            destination = destination_dir / source.name
            source_sql = source.read_text(encoding="utf-8")
            if destination.exists():
                root_sql = destination.read_text(encoding="utf-8")
                if source_sql != root_sql:
                    conflicts.append((source.name, root_sql, source_sql))
                continue
            shutil.copy2(source, destination)
            copied.append(source.name)
        return MigrationSyncResult(True, tuple(copied), tuple(conflicts))
    except (OSError, UnicodeError) as error:
        return MigrationSyncResult(False, output=f"Could not synchronize personal migrations: {error}")


def push_migrations(
    directory: Path,
    *,
    executable: str = "supabase",
    env: dict[str, str] | None = None,
    database_url: str | None = None,
) -> PushResult:
    """Run non-interactive `supabase db push --yes` from the selected CLI root."""
    resolved_executable = shutil.which(executable)
    if resolved_executable is None:
        return PushResult(False, f"{executable} is not available on PATH.")
    try:
        command = [resolved_executable, "db", "push", "--yes"]
        if database_url:
            command.extend(["--db-url", database_url])
        process = subprocess.run(
            command,
            cwd=directory,
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError as error:
        return PushResult(False, str(error))
    output = "\n".join(part.strip() for part in (process.stdout, process.stderr) if part.strip())
    return PushResult(process.returncode == 0, output)
