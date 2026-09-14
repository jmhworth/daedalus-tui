"""Initialize a Daedalus-compatible project under the TUI launch root."""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
import uuid
from pathlib import Path
from typing import Callable


TUI_ROOT = Path(__file__).resolve().parents[1]
PARAMETER_PATH = TUI_ROOT / "parameter_files" / "daedalus-tui-project-initialization.toml"
TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates" / "project-initializer"
REQUEST_MARKER = "daedalus-initialization-request-id"
DIAGNOSTIC_LIMIT = 8_000
PROJECT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ProgressCallback = Callable[[dict], None]


def load_initializer_settings() -> dict:
    with PARAMETER_PATH.open("rb") as source:
        return tomllib.load(source)


def validate_project_name(project_name: object, maximum_length: int) -> str:
    if not isinstance(project_name, str):
        raise ValueError("Project name must be a string.")
    normalized = project_name.strip().lower()
    if not normalized:
        raise ValueError("Project name is required.")
    if len(normalized) > maximum_length:
        raise ValueError(f"Project name must be at most {maximum_length} characters.")
    if normalized in {".", ".."} or normalized.startswith("."):
        raise ValueError("Project name cannot be a dot path or hidden directory.")
    if "/" in normalized or "\\" in normalized or not PROJECT_NAME_PATTERN.fullmatch(normalized):
        raise ValueError("Use lowercase letters, numbers, and internal hyphens only.")
    return normalized


def resolve_destination(execution_root: Path, project_name: str) -> Path:
    root = execution_root.resolve()
    destination = (root / project_name).resolve()
    if destination.parent != root:
        raise ValueError("Project destination must be a direct child of the execution root.")
    return destination


def result_shape(
    request_id: str,
    project_name: str,
    destination: Path,
    status: str,
    steps: list[dict],
    error: str | None = None,
    github_url: str | None = None,
) -> dict:
    return {
        "requestId": request_id,
        "projectName": project_name,
        "projectDirectory": str(destination),
        "status": status,
        "githubUrl": github_url,
        "error": error,
        "steps": steps,
    }


def step(name: str, command: list[str], status: str = "pending") -> dict:
    return {
        "name": name,
        "status": status,
        "command": command,
        "exitCode": None,
        "stdout": "",
        "stderr": "",
    }


def publish(progress: ProgressCallback | None, result: dict) -> None:
    if progress:
        progress({**result, "steps": [dict(item) for item in result["steps"]]})


def run_step(
    current_step: dict,
    directory: Path,
    base_result: dict,
    progress: ProgressCallback | None,
    run_process,
    keep_stdout: bool = False,
) -> bool:
    current_step["status"] = "running"
    publish(progress, base_result)
    completed = run_process(
        current_step["command"],
        cwd=str(directory),
        capture_output=True,
        text=True,
        shell=False,
    )
    current_step["exitCode"] = completed.returncode
    current_step["status"] = "success" if completed.returncode == 0 else "failed"
    if keep_stdout:
        artifacts = [
            token.rstrip("/")
            for token in completed.stdout.split()
            if token.startswith("https://github.com/") or token.startswith("git@github.com:")
        ]
        current_step["stdout"] = "\n".join(artifacts)[-DIAGNOSTIC_LIMIT:]
    else:
        current_step["stdout"] = ""
    current_step["stderr"] = completed.stderr[-DIAGNOSTIC_LIMIT:] if completed.returncode else ""
    publish(progress, base_result)
    return completed.returncode == 0


def matching_request_marker(destination: Path, request_id: str) -> bool:
    marker = destination / ".git" / REQUEST_MARKER
    return marker.is_file() and marker.read_text(encoding="utf-8").strip() == request_id


def safe_cleanup_temporary(root: Path, temporary: Path, project_name: str) -> None:
    resolved_root = root.resolve()
    resolved_temporary = temporary.resolve()
    prefix = f".{project_name}.daedalus-init-"
    if resolved_temporary.parent != resolved_root or not resolved_temporary.name.startswith(prefix):
        raise ValueError("Refusing to clean an unrecognized initialization path.")
    if resolved_temporary.exists():
        shutil.rmtree(resolved_temporary)


def materialize_templates(destination: Path, project_name: str, settings: dict) -> None:
    shutil.copytree(TEMPLATE_ROOT, destination)
    readme = destination / "README.md"
    gitignore = destination / ".gitignore"
    daedalus = destination / ".daedalus"
    if settings["generate_readme"]:
        readme.write_text(
            readme.read_text(encoding="utf-8").replace("{{PROJECT_NAME}}", project_name),
            encoding="utf-8",
        )
    elif readme.exists():
        readme.unlink()
    if not settings["generate_gitignore"] and gitignore.exists():
        gitignore.unlink()
    if not settings["generate_daedalus"] and daedalus.exists():
        daedalus.unlink()


def find_github_url(stdout: str, destination: Path, run_process) -> str | None:
    for token in stdout.split():
        if token.startswith("https://github.com/") or token.startswith("git@github.com:"):
            return normalize_github_url(token)
    try:
        remote = run_process(
            ["git", "remote", "get-url", "origin"],
            cwd=str(destination),
            capture_output=True,
            text=True,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return normalize_github_url(remote.stdout.strip()) if remote.returncode == 0 else None


def normalize_github_url(value: str) -> str | None:
    url = value.strip().rstrip("/")
    if not url:
        return None
    if url.startswith("git@github.com:"):
        url = f"https://github.com/{url.removeprefix('git@github.com:')}"
    return url.removesuffix(".git")


def initialize_project(
    request: dict,
    progress: ProgressCallback | None = None,
    execution_root: Path | None = None,
    run_process=subprocess.run,
    find_executable=shutil.which,
) -> dict:
    settings = load_initializer_settings()
    request_id = request.get("requestId")
    try:
        uuid.UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Initialization requestId must be a UUID.")
    request_id = str(request_id)
    project_name = validate_project_name(
        request.get("projectName"),
        int(settings["maximum_project_name_length"]),
    )
    create_github = request.get("createGitHubRepository", False)
    if not isinstance(create_github, bool):
        raise ValueError("createGitHubRepository must be a boolean.")

    root = (execution_root or Path.cwd()).resolve()
    destination = resolve_destination(root, project_name)
    temporary = root / f".{project_name}.daedalus-init-{request_id}"
    local_commands = [
        ("graphify-codex-install", ["graphify", "codex", "install"]),
        ("graphify-cursor-install", ["graphify", "cursor", "install"]),
        ("git-init", ["git", "init", "-b", str(settings["initial_branch"])]),
        ("git-add", ["git", "add", "."]),
        ("git-commit", ["git", "commit", "-m", str(settings["initial_commit_message"])]),
    ]
    steps = [step(name, command) for name, command in local_commands]
    if create_github:
        steps.append(step("github-create", [
            "gh", "repo", "create", project_name, "--private", "--source=.",
            "--remote=origin", "--push",
        ]))
    base_result = result_shape(request_id, project_name, destination, "running", steps)

    required = [("git", "Git"), ("graphify", "Graphify")]
    if create_github:
        required.append(("gh", "GitHub CLI"))
    missing = [label for executable, label in required if not find_executable(executable)]
    if missing:
        return result_shape(
            request_id, project_name, destination, "failed", steps,
            f"Missing required executable: {', '.join(missing)}.",
        )

    if create_github:
        authentication = step("github-auth-status", ["gh", "auth", "status"])
        steps.insert(0, authentication)
        if not run_step(authentication, root, base_result, progress, run_process):
            base_result["status"] = "failed"
            base_result["error"] = "GitHub CLI authentication is unavailable."
            return base_result

    local_complete = False
    if destination.exists():
        if not destination.is_dir() or not matching_request_marker(destination, request_id):
            return result_shape(
                request_id, project_name, destination, "failed", steps,
                "The destination already exists and is not owned by this request.",
            )
        local_complete = True

    if temporary.exists() and not local_complete:
        safe_cleanup_temporary(root, temporary, project_name)

    if not local_complete:
        try:
            materialize_templates(temporary, project_name, settings)
            for current_step in steps:
                if current_step["name"] == "github-auth-status":
                    continue
                if current_step["name"] == "github-create":
                    break
                if not run_step(current_step, temporary, base_result, progress, run_process):
                    safe_cleanup_temporary(root, temporary, project_name)
                    base_result["status"] = "failed"
                    base_result["error"] = f"Initialization failed during {current_step['name']}."
                    return base_result
                if current_step["name"] == "git-init":
                    (temporary / ".git" / REQUEST_MARKER).write_text(request_id, encoding="utf-8")
            temporary.rename(destination)
        except (OSError, subprocess.SubprocessError) as error:
            safe_cleanup_temporary(root, temporary, project_name)
            base_result["status"] = "failed"
            base_result["error"] = f"Local initialization failed: {error}"
            return base_result
    else:
        for current_step in steps:
            if current_step["name"] not in {"github-auth-status", "github-create"}:
                current_step["status"] = "skipped"
                current_step["stderr"] = "Local initialization already completed for this request."

    if not create_github:
        base_result["status"] = "success"
        publish(progress, base_result)
        return base_result

    existing_url = find_github_url("", destination, run_process)
    github_step = next(item for item in steps if item["name"] == "github-create")
    if existing_url:
        github_step["status"] = "skipped"
        github_step["stderr"] = "Origin already exists; GitHub creation was not repeated."
        base_result["githubUrl"] = existing_url
        base_result["status"] = "success"
        publish(progress, base_result)
        return base_result

    try:
        github_succeeded = run_step(
            github_step, destination, base_result, progress, run_process, keep_stdout=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        github_step["status"] = "failed"
        github_step["stderr"] = str(error)[-DIAGNOSTIC_LIMIT:]
        github_succeeded = False
    if not github_succeeded:
        base_result["status"] = "partial_success"
        origin_url = find_github_url("", destination, run_process)
        base_result["githubUrl"] = origin_url
        base_result["error"] = (
            "Local project initialized, but GitHub setup failed. "
            + ("An origin exists; retry the push." if origin_url
               else f"Rerun: gh repo create {project_name} --private --source=. --remote=origin --push")
        )
        publish(progress, base_result)
        return base_result

    base_result["githubUrl"] = find_github_url(str(github_step["stdout"]), destination, run_process)
    base_result["status"] = "success"
    publish(progress, base_result)
    return base_result
