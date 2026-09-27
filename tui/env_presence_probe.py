"""Child-process probe for Daedalus TUI Supabase env key presence.

Invoke as ``python -m tui.env_presence_probe``. Exit ``0`` when required keys
resolve from the TUI package root's ``.env`` file; otherwise exit ``1`` and
print a key-name-only diagnostic on stderr (never secret values).

The probe deliberately ignores process ``SUPABASE_*`` overrides so Continue
confirms the project file was saved, not that keys happen to exist in the
parent shell. Daedalus uses the exit code so the parent TUI process does not
need to load ``.env`` contents just to decide whether Continue may proceed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .environment import read_env_file
from .personal_supabase import load_personal_supabase_settings, resolve_personal_supabase_environment


def main() -> int:
    require_database_access = os.environ.get("DAEDALUS_ENV_PROBE_REQUIRE_DB", "1") != "0"
    settings = load_personal_supabase_settings()
    values = read_env_file(Path(__file__).resolve().parents[1] / ".env")
    _resolved, error = resolve_personal_supabase_environment(
        values,
        settings,
        require_database_access=require_database_access,
    )
    if error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
