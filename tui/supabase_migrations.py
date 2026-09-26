"""Orchestration-owned Supabase migration push for target project worktrees."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


MIGRATIONS_PATH = "supabase/migrations/"


@dataclass(frozen=True)
class PushResult:
    succeeded: bool
    output: str = ""


def migrations_pending(worktree: Path, base_commit: str) -> bool:
    """Return True when the worktree differs from base under supabase/migrations/."""
    try:
        process = subprocess.run(
            ["git", "diff", "--name-only", base_commit, "--", MIGRATIONS_PATH],
            cwd=worktree,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if process.returncode != 0:
        return False
    return bool(process.stdout.strip())


def push_migrations(
    directory: Path,
    *,
    executable: str = "supabase",
    env: dict[str, str] | None = None,
) -> PushResult:
    """Run non-interactive `supabase db push --yes` in the target worktree."""
    resolved_executable = shutil.which(executable)
    if resolved_executable is None:
        return PushResult(False, f"{executable} is not available on PATH.")
    try:
        process = subprocess.run(
            [resolved_executable, "db", "push", "--yes"],
            cwd=directory,
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError as error:
        return PushResult(False, str(error))
    output = "\n".join(part.strip() for part in (process.stdout, process.stderr) if part.strip())
    return PushResult(process.returncode == 0, output)
