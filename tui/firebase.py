"""File-only Firebase backend registration plus the orchestration deploy step.

Registration writes configuration, security rules, and a ``.daedalus`` marker so
agents know which backend a project targets. Applying those rules remotely is
orchestration's job, mirroring how Supabase migrations are pushed only after
verification passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import shutil
import subprocess
import tomllib

from .project_config import DAEDALUS_CONFIG_FILENAME

TUI_ROOT = Path(__file__).resolve().parents[1]
PARAMETER_PATH = TUI_ROOT / "parameter_files" / "daedalus-tui-firebase.toml"
PROFILE_RELATIVE_PATHS = (
    Path(".agents") / "profiles" / "coding.md",
    Path(".agents") / "profiles" / "architecture.md",
)
SECTION_TABLE = "firebase"


@dataclass(frozen=True)
class FirebaseStatus:
    """Registration marker loaded from a target project's ``.daedalus`` file."""

    registered: bool
    project_id: str | None = None


@dataclass(frozen=True)
class RegistrationResult:
    """Outcome of scaffolding Firebase files into a project tree."""

    status: str
    project_id: str
    message: str
    project_root: Path
    already_registered: bool = False


@dataclass(frozen=True)
class DeployResult:
    succeeded: bool
    output: str = ""


def load_firebase_settings() -> dict:
    """Load tunables for registration and deployment from the parameter file."""
    with PARAMETER_PATH.open("rb") as source:
        return tomllib.load(source)


def _validate_project_id(project_id: object, maximum_length: int) -> str:
    # Imported lazily to avoid a circular import with project_initializer.
    from .project_initializer import validate_project_name

    return validate_project_name(project_id, maximum_length)


def project_id_from_project_root(project_root: Path, maximum_length: int | None = None) -> str:
    """Derive and validate the Firebase project id from the directory slug."""
    settings = load_firebase_settings()
    limit = int(maximum_length if maximum_length is not None else settings["maximum_project_id_length"])
    return _validate_project_id(project_root.resolve().name, limit)


def load_firebase_status(project_root: Path) -> FirebaseStatus:
    """Return the ``[firebase]`` marker, or an unregistered default."""
    path = project_root / DAEDALUS_CONFIG_FILENAME
    if not path.is_file():
        return FirebaseStatus(registered=False)
    try:
        with path.open("rb") as source:
            values = tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"Could not read project configuration {path}: {error}") from error

    table = values.get(SECTION_TABLE, {})
    if table in (None, {}):
        return FirebaseStatus(registered=False)
    if not isinstance(table, dict):
        raise ValueError(f"{path} {SECTION_TABLE} must be a table.")

    registered = table.get("registered", False)
    if not isinstance(registered, bool):
        raise ValueError(f"{path} {SECTION_TABLE}.registered must be a boolean.")
    project_id = table.get("project_id")
    if project_id is not None and (not isinstance(project_id, str) or not project_id.strip()):
        raise ValueError(f"{path} {SECTION_TABLE}.project_id must be a non-empty string when set.")
    return FirebaseStatus(
        registered=registered,
        project_id=project_id.strip() if isinstance(project_id, str) else None,
    )


def is_firebase_registered(project_root: Path, project_id: str | None = None) -> bool:
    """True when the project is marked registered for ``project_id`` (or any)."""
    try:
        status = load_firebase_status(project_root)
    except ValueError:
        return False
    if not status.registered:
        return False
    if project_id is None:
        return True
    return status.project_id == project_id


def register_firebase(project_root: Path, project_id: str | None = None) -> RegistrationResult:
    """Scaffold Firebase config, rules, env placeholders, profiles, and a marker.

    Remote apply is intentionally out of scope; orchestration owns
    ``firebase deploy`` after verification passes.
    """
    root = project_root.expanduser().resolve()
    settings = load_firebase_settings()
    try:
        if project_id is None:
            name = project_id_from_project_root(root)
        else:
            name = _validate_project_id(project_id, int(settings["maximum_project_id_length"]))
    except ValueError as error:
        return RegistrationResult("failed", str(project_id or ""), str(error), root)

    try:
        status = load_firebase_status(root)
    except ValueError as error:
        return RegistrationResult("failed", name, str(error), root)

    if status.registered and status.project_id == name:
        return RegistrationResult(
            "success",
            name,
            f"Firebase project {name!r} is already registered.",
            root,
            already_registered=True,
        )
    if status.registered and status.project_id and status.project_id != name:
        return RegistrationResult(
            "failed",
            name,
            (
                f"Project is already registered for Firebase project {status.project_id!r}; "
                f"refusing to register {name!r}."
            ),
            root,
        )

    conflict = _firebase_layout_conflict(root, settings)
    if conflict:
        return RegistrationResult("failed", name, conflict, root)

    try:
        _ensure_firebase_scaffold(root, settings)
        _ensure_env_example(root, name, settings)
        _ensure_profile_guidance(root, name, settings)
        _write_registration_marker(root, name)
    except (OSError, ValueError) as error:
        return RegistrationResult("failed", name, str(error), root)

    return RegistrationResult("success", name, f"Registered Firebase project {name!r}.", root)


def profile_guidance_section(project_id: str, settings: dict | None = None) -> str:
    """Return the markdown section appended to coding/architecture profiles."""
    values = settings or load_firebase_settings()
    heading = str(values["profile_section_heading"])
    env_key = str(values["env_project_id_key"])
    targets = ", ".join(str(target) for target in values["deploy_targets"])
    return (
        f"{heading}\n\n"
        "This project uses Firebase as its backend. Use the Firebase SDKs and "
        "Firestore security rules rather than a SQL database or Supabase client.\n\n"
        f"- Read the project id from `{env_key}` in `.env` (expected value: `{project_id}`).\n"
        f"- Keep Firestore access rules in `{values['rules_filename']}` and composite "
        f"indexes in `{values['indexes_filename']}`.\n"
        "- Security rules deny by default; widen them deliberately and never ship an "
        "open `allow read, write: if true;` rule.\n"
        "- Agents must not run `firebase deploy`; orchestration owns the remote apply of "
        f"`{targets}` after verification when the Firebase files change.\n"
        "- Never commit service-account JSON or API keys; `.env` holds them locally.\n"
    )


def firebase_changes_pending(worktree: Path, base_commit: str, settings: dict | None = None) -> bool:
    """Return True when the worktree differs from base under the Firebase files."""
    values = settings or load_firebase_settings()
    paths = [str(path) for path in values["watched_paths"]]
    try:
        process = subprocess.run(
            ["git", "diff", "--name-only", base_commit, "--", *paths],
            cwd=worktree,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if process.returncode != 0:
        return False
    return bool(process.stdout.strip())


def deploy_firebase(
    directory: Path,
    *,
    executable: str = "firebase",
    project_id: str | None = None,
    settings: dict | None = None,
    env: dict[str, str] | None = None,
) -> DeployResult:
    """Run non-interactive `firebase deploy --only <targets>` in the worktree."""
    values = settings or load_firebase_settings()
    if shutil.which(executable) is None:
        return DeployResult(False, f"{executable} is not available on PATH.")
    targets = ",".join(str(target) for target in values["deploy_targets"])
    command = [executable, "deploy", "--only", targets, "--non-interactive"]
    placeholder = str(values["config_project_id_placeholder"])
    if project_id and project_id != placeholder:
        command.extend(["--project", project_id])
    try:
        process = subprocess.run(
            command,
            cwd=directory,
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError as error:
        return DeployResult(False, str(error))
    output = "\n".join(part.strip() for part in (process.stdout, process.stderr) if part.strip())
    return DeployResult(process.returncode == 0, output)


def _firebase_layout_conflict(root: Path, settings: dict) -> str | None:
    config = root / str(settings["config_filename"])
    if config.exists() and not config.is_file():
        return f"{settings['config_filename']} exists but is not a file."
    if config.is_file():
        try:
            payload = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return f"Existing {settings['config_filename']} is not readable JSON: {error}"
        if not isinstance(payload, dict):
            return f"Existing {settings['config_filename']} must contain a JSON object."
    return None


def _ensure_firebase_scaffold(root: Path, settings: dict) -> None:
    config_path = root / str(settings["config_filename"])
    rules_name = str(settings["rules_filename"])
    indexes_name = str(settings["indexes_filename"])
    storage_rules_name = str(settings["storage_rules_filename"])

    if config_path.exists():
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        payload = {}
    payload.setdefault("firestore", {"rules": rules_name, "indexes": indexes_name})
    payload.setdefault("storage", {"rules": storage_rules_name})
    config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    rules_path = root / rules_name
    if not rules_path.exists():
        rules_path.write_text(
            (
                "rules_version = '2';\n\n"
                "// Scaffolded by Daedalus Firebase registration.\n"
                "// Deny by default; widen these rules deliberately per collection.\n"
                "service cloud.firestore {\n"
                "  match /databases/{database}/documents {\n"
                "    match /{document=**} {\n"
                "      allow read, write: if false;\n"
                "    }\n"
                "  }\n"
                "}\n"
            ),
            encoding="utf-8",
        )

    indexes_path = root / indexes_name
    if not indexes_path.exists():
        indexes_path.write_text(
            json.dumps({"indexes": [], "fieldOverrides": []}, indent=2) + "\n",
            encoding="utf-8",
        )

    storage_path = root / storage_rules_name
    if not storage_path.exists():
        storage_path.write_text(
            (
                "rules_version = '2';\n\n"
                "// Scaffolded by Daedalus Firebase registration. Deny by default.\n"
                "service firebase.storage {\n"
                "  match /b/{bucket}/o {\n"
                "    match /{allPaths=**} {\n"
                "      allow read, write: if false;\n"
                "    }\n"
                "  }\n"
                "}\n"
            ),
            encoding="utf-8",
        )


def _ensure_env_example(root: Path, project_id: str, settings: dict) -> None:
    path = root / ".env.example"
    block = _env_example_block(project_id, settings)
    if not path.exists():
        path.write_text(block, encoding="utf-8")
        return

    existing = path.read_text(encoding="utf-8")
    project_key = str(settings["env_project_id_key"])
    match = re.search(rf"(?m)^{re.escape(project_key)}=(.*)$", existing)
    if match:
        current = match.group(1).strip()
        if current and current != project_id:
            raise ValueError(
                f".env.example already sets {project_key}={current!r}; "
                f"refusing to overwrite with {project_id!r}."
            )
        if current == project_id:
            return
        updated = re.sub(
            rf"(?m)^{re.escape(project_key)}=.*$",
            f"{project_key}={project_id}",
            existing,
            count=1,
        )
        path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")
        return

    path.write_text(existing.rstrip() + "\n\n" + block, encoding="utf-8")


def _env_example_block(project_id: str, settings: dict) -> str:
    return (
        "# Firebase project settings (fill in from the Firebase console).\n"
        "# Never commit real keys or service-account JSON; copy this file to .env locally.\n"
        f"{settings['env_project_id_key']}={project_id}\n"
        f"{settings['env_api_key_key']}=\n"
        f"{settings['env_app_id_key']}=\n"
        f"{settings['env_auth_domain_key']}=\n"
        f"{settings['env_storage_bucket_key']}=\n"
    )


def _ensure_profile_guidance(root: Path, project_id: str, settings: dict) -> None:
    section = profile_guidance_section(project_id, settings)
    heading = str(settings["profile_section_heading"])
    for relative in PROFILE_RELATIVE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if heading in text:
                if project_id not in text.split(heading, 1)[1]:
                    raise ValueError(
                        f"{relative} already has a Firebase Backend section that does "
                        f"not reference {project_id!r}."
                    )
                continue
            path.write_text(text.rstrip() + "\n\n" + section, encoding="utf-8")
        else:
            path.write_text(section, encoding="utf-8")


def _write_registration_marker(root: Path, project_id: str) -> None:
    path = root / DAEDALUS_CONFIG_FILENAME
    section = f"[{SECTION_TABLE}]\nregistered = true\nproject_id = \"{project_id}\"\n"
    if not path.exists():
        path.write_text(section, encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"(?ms)^\[{re.escape(SECTION_TABLE)}\]\n.*?(?=^\[|\Z)")
    if pattern.search(text):
        updated = pattern.sub(section + "\n", text, count=1)
    else:
        updated = text.rstrip() + "\n\n" + section
    path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")


__all__ = [
    "DeployResult",
    "FirebaseStatus",
    "RegistrationResult",
    "deploy_firebase",
    "firebase_changes_pending",
    "is_firebase_registered",
    "load_firebase_settings",
    "load_firebase_status",
    "profile_guidance_section",
    "project_id_from_project_root",
    "register_firebase",
]
