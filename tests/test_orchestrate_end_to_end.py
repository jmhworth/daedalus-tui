"""Orchestrate Mode against a real temporary Git repository.

The fake runner never talks to a model: planner turns come from a script and
worker turns edit the files their card names, tick the card, and report.
Everything else — worktrees, verification, integration, the resolver, and
promotion — is the real orchestration pipeline.
"""

import json
import re
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tui.agent_runner import AgentResult
from tui.config import OrchestrateSettings
from tui.local_storage import LocalStorage
from tui.memory import TaskMemoryStore
from tui.orchestrate_coordinator import OrchestrateCoordinator
from tui.orchestrator import OrchestrationSettings
from tui.task_coordinator import TaskCoordinator


OPERATOR_PROMPT = "OPERATOR_PROMPT_SENTINEL: add three modules."
PLANNER = ("claude", "claude-fable-5-1", "high")
WORKER = ("claude", "claude-opus-5", "high")
CARD_ID = re.compile(r"^# (t\d+) —", re.MULTILINE)


def git(repository, *arguments):
    return subprocess.run(
        ["git", *arguments], cwd=repository, capture_output=True, text=True, check=True
    ).stdout.strip()


def payload(summary, tasks, done=False):
    return (
        "BEGIN_DAEDALUS_ORCHESTRATION\n"
        + json.dumps({"summary": summary, "tasks": tasks, "done": done})
        + "\nEND_DAEDALUS_ORCHESTRATION"
    )


def card(task_id, scope, depends_on=()):
    return {
        "id": task_id,
        "title": f"Write {task_id}",
        "goal": f"Create {scope} with a {task_id} function.",
        "checklist": [f"{scope} exists", f"{task_id} function defined"],
        "file_scope": [scope],
        "read_first": [],
        "interfaces": f"def {task_id}() -> str",
        "verify": "true",
        "depends_on": list(depends_on),
    }


def report(task_id, files):
    return (
        "Done.\n\nBEGIN_DAEDALUS_WORKER_REPORT\n"
        + json.dumps({"task": task_id, "status": "done", "checklist": [True, True], "files_changed": files, "errors": "", "notes": ""})
        + "\nEND_DAEDALUS_WORKER_REPORT"
    )


class FileEditingRunner:
    """Workers edit the file their card names; an optional extra edit strays outside scope."""

    def __init__(self, planner_responses, stray_edits=None):
        self.planner_responses = list(planner_responses)
        self.stray_edits = stray_edits or {}
        self.lock = threading.Lock()
        self.planner_prompts = []
        self.worker_prompts = []
        self.worker_order = []
        self.resolver_models = []
        self.active = 0
        self.max_active = 0

    def run(self, request, on_event=None):
        prompt = request.prompt
        if "TASK_MODE: orchestrate-plan" in prompt:
            with self.lock:
                self.planner_prompts.append(prompt)
                index = len(self.planner_prompts) - 1
            return AgentResult("claude", 0, self.planner_responses[min(index, len(self.planner_responses) - 1)], tokens_consumed=7)
        if "TASK_MODE: integrating" in prompt:
            with self.lock:
                self.resolver_models.append(request.model)
            for path in request.directory.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if "<<<<<<<" in text:
                    merged = "\n".join(
                        line for line in text.splitlines()
                        if not line.startswith(("<<<<<<<", "=======", ">>>>>>>"))
                    )
                    path.write_text(merged + "\n", encoding="utf-8")
            return AgentResult("claude", 0, "Resolved the conflict.", tokens_consumed=3)
        match = CARD_ID.search(prompt)
        card_id = match.group(1) if match else "?"
        with self.lock:
            self.worker_prompts.append(prompt)
            self.worker_order.append(card_id)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        scope = re.search(r"^## File scope\n- (.+)$", prompt, re.MULTILINE).group(1)
        target = request.directory / scope
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"def {card_id}() -> str:\n    return {card_id!r}\n", encoding="utf-8")
        files = [scope]
        for path, text in self.stray_edits.get(card_id, ()):
            stray = request.directory / path
            stray.parent.mkdir(parents=True, exist_ok=True)
            stray.write_text(text, encoding="utf-8")
            files.append(path)
        card_path = request.directory / ".daedalus-orchestration" / "task.md"
        card_path.write_text(card_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        time.sleep(0.05)
        with self.lock:
            self.active -= 1
        return AgentResult("claude", 0, report(card_id, files), tokens_consumed=4)


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        root = Path(self._directory.name).resolve()
        self.repository = root / "project"
        self.repository.mkdir()
        git(self.repository, "init", "-q", "-b", "main")
        git(self.repository, "config", "user.email", "tests@example.com")
        git(self.repository, "config", "user.name", "Daedalus Tests")
        (self.repository / "src").mkdir()
        (self.repository / "src" / "shared.py").write_text("VALUE = 0\n", encoding="utf-8")
        (self.repository / "README.md").write_text("# project\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-q", "-m", "initial")
        self.memory = TaskMemoryStore(root / ".daedalus-memory.json")
        self.storage = LocalStorage(root / "storage")
        self.settings = OrchestrationSettings(
            verification_commands=(("true",),),
            graphify_update_enabled=False,
            supabase_db_push_enabled=False,
            firebase_deploy_enabled=False,
            dirty_primary_push_enabled=False,
            max_concurrent_tasks=4,
        )

    def tearDown(self):
        self._directory.cleanup()

    def run_session(self, runner, max_workers=2):
        tasks = TaskCoordinator(self.repository, runner, self.settings, memory_path=self.memory.path)
        coordinator = OrchestrateCoordinator(
            tasks, runner, self.settings, OrchestrateSettings(), self.storage, self.memory
        )
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=max_workers)
            deadline = time.time() + 60
            while session.active and time.time() < deadline:
                time.sleep(0.05)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
        return session, tasks

    def committed_paths(self):
        output = git(self.repository, "log", "--all", "--name-only", "--pretty=format:")
        return {line.strip() for line in output.splitlines() if line.strip()}

    def test_three_cards_promote_in_dependency_order_without_card_files(self):
        runner = FileEditingRunner(
            [
                payload(
                    "Three modules; t3 imports t2.",
                    [card("t1", "src/one.py"), card("t2", "src/two.py"), card("t3", "src/three.py", depends_on=("t2",))],
                ),
                payload("All promoted.", [], done=True),
            ]
        )
        session, tasks = self.run_session(runner)

        self.assertEqual(session.status, "completed", session.error)
        self.assertEqual({card_id: item.status for card_id, item in session.cards.items()}, {"t1": "promoted", "t2": "promoted", "t3": "promoted"})
        self.assertEqual(session.cards["t3"].ticks, (True, True))
        self.assertLessEqual(runner.max_active, 2)
        self.assertEqual(runner.worker_order[-1], "t3")
        self.assertEqual(set(runner.worker_order[:2]), {"t1", "t2"})
        # The operating branch carries all three promotions, t3 after t2.
        subjects = git(self.repository, "log", "--format=%s", "main").splitlines()
        self.assertEqual(subjects[-1], "initial")
        positions = {card_id: next(index for index, subject in enumerate(subjects) if f"{card_id}: Write {card_id}" in subject) for card_id in ("t1", "t2", "t3")}
        self.assertLess(positions["t3"], positions["t2"])  # newest first
        for name in ("one", "two", "three"):
            self.assertTrue((self.repository / "src" / f"{name}.py").is_file(), name)
        self.assertTrue(all(record.status == "completed" for record in tasks.tasks()))
        self.assertEqual(runner.resolver_models, [])
        self.assertTrue(all(OPERATOR_PROMPT not in prompt for prompt in runner.worker_prompts))
        # No card file ever reached a commit on any branch.
        self.assertFalse({path for path in self.committed_paths() if path.startswith(".daedalus-orchestration")})
        self.assertEqual(git(self.repository, "status", "--porcelain"), "")
        self.assertEqual(session.tokens_planner, 14)
        self.assertEqual(session.tokens_workers, 12)

    def test_out_of_scope_edit_conflicts_and_the_planner_model_resolves_it(self):
        """The parser rejects overlapping scopes, so the conflict comes from a stray edit."""
        runner = FileEditingRunner(
            [
                payload("Two independent cards.", [card("t1", "src/one.py"), card("t2", "src/two.py")]),
                payload("All promoted.", [], done=True),
            ],
            stray_edits={
                "t1": [("src/shared.py", "VALUE = 1  # from t1\n")],
                "t2": [("src/shared.py", "VALUE = 2  # from t2\n")],
            },
        )
        session, tasks = self.run_session(runner)

        self.assertEqual(session.status, "completed", session.error)
        self.assertEqual({item.status for item in session.cards.values()}, {"promoted"})
        self.assertGreaterEqual(len(runner.resolver_models), 1)
        self.assertEqual(set(runner.resolver_models), {"claude-fable-5-1"})
        subjects = git(self.repository, "log", "--format=%s", "main").splitlines()
        self.assertTrue(any("integration resolver" in subject for subject in subjects), subjects)
        shared = (self.repository / "src" / "shared.py").read_text(encoding="utf-8")
        self.assertNotIn("<<<<<<<", shared)
        self.assertIn("VALUE = 1", shared)
        self.assertIn("VALUE = 2", shared)
        self.assertFalse({path for path in self.committed_paths() if path.startswith(".daedalus-orchestration")})
        self.assertTrue(all(record.status == "completed" for record in tasks.tasks()))


if __name__ == "__main__":
    unittest.main()
