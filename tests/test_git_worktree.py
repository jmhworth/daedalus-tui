import unittest
import tempfile
from pathlib import Path
from unittest.mock import call, patch

from tui.git_worktree import (
    DIRTY_PRIMARY_COMMIT_MESSAGE,
    GitWorktreeError,
    GitWorktreeManager,
    WorktreeContext,
)
from tui.project_config import ProjectWorktreeSettings


def status_process(stdout: str):
    """A CompletedProcess-alike carrying raw `git status --porcelain` stdout."""
    return type("Process", (), {"returncode": 0, "stdout": stdout, "stderr": ""})()


class GitWorktreeTests(unittest.TestCase):
    def test_list_local_branches_returns_short_ref_names(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.return_value = type(
                "Process",
                (),
                {"returncode": 0, "stdout": "main\njames\ndevelop\n", "stderr": ""},
            )()
            from tui.git_worktree import list_local_branches

            self.assertEqual(list_local_branches(Path("/repo")), ["main", "james", "develop"])
            self.assertEqual(
                run.call_args.args[0],
                ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"],
            )

    def test_list_local_branches_returns_empty_on_git_failure(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.return_value = type(
                "Process",
                (),
                {"returncode": 128, "stdout": "", "stderr": "not a git repository"},
            )()
            from tui.git_worktree import list_local_branches

            self.assertEqual(list_local_branches(Path("/repo")), [])

    def test_create_uses_primary_sha_and_task_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = GitWorktreeManager(Path(directory) / "repo")
            with patch.object(manager, "_validate_primary"), patch.object(manager, "git_output", return_value="abc123"), patch.object(manager, "run_git") as run_git:
                context = manager.create("task-1")

            self.assertEqual(context.base_commit, "abc123")
            self.assertEqual(context.branch_name, "agent/task-task-1")
            self.assertEqual(context.path, Path(directory).resolve() / ".daedalus-worktrees" / "repo" / "task-task-1")
            self.assertEqual(run_git.call_args.args[0][:4], ["worktree", "add", "-b", "agent/task-task-1"])

    def test_primary_validation_commits_and_pushes_a_dirty_repository(self):
        """A dirty operating branch starts the task instead of failing it."""
        manager = GitWorktreeManager(Path("/repo"))
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "git_output", side_effect=["main", "changed.py"]
        ), patch.object(
            manager, "run_git", return_value=status_process(" M changed.py\n")
        ) as run_git, patch("tui.git_worktree.push_branch") as push_branch:
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            manager._validate_primary()

        commands = [call.args[0] for call in run_git.call_args_list]
        self.assertIn(["add", "-A", "--", "changed.py"], commands)
        self.assertIn(["commit", "-m", DIRTY_PRIMARY_COMMIT_MESSAGE], commands)
        push_branch.assert_called_once_with(Path("/repo").resolve(), "main", "origin")

    def test_primary_autocommit_leaves_daedalus_runtime_files_untracked(self):
        """Staging is limited to real changes so the debug log stays untracked."""
        manager = GitWorktreeManager(Path("/repo"))
        status = " M .daedalus-debug.log\n M tui/app.py\n"
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "git_output", side_effect=["main", "tui/app.py"]
        ), patch.object(manager, "run_git", return_value=status_process(status)) as run_git, patch(
            "tui.git_worktree.push_branch"
        ):
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            manager.validate_primary()

        commands = [call.args[0] for call in run_git.call_args_list]
        self.assertIn(["add", "-A", "--", "tui/app.py"], commands)

    def test_primary_autocommit_reports_a_failed_push_without_blocking(self):
        notices: list[tuple[str, str]] = []
        manager = GitWorktreeManager(
            Path("/repo"), on_notice=lambda message, kind="status": notices.append((message, kind))
        )
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "git_output", side_effect=["main", "changed.py"]
        ), patch.object(manager, "run_git", return_value=status_process(" M changed.py\n")), patch(
            "tui.git_worktree.push_branch", side_effect=GitWorktreeError("Authentication failed")
        ):
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            manager.validate_primary()

        self.assertTrue(any("Authentication failed" in message for message, _ in notices))

    def test_primary_autocommit_keeps_the_commit_local_without_a_remote(self):
        notices: list[tuple[str, str]] = []
        manager = GitWorktreeManager(
            Path("/repo"), on_notice=lambda message, kind="status": notices.append((message, kind))
        )
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "git_output", side_effect=["main", "changed.py"]
        ), patch.object(manager, "run_git", return_value=status_process(" M changed.py\n")), patch(
            "tui.git_worktree.push_branch"
        ) as push_branch:
            run.side_effect = [
                type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("Process", (), {"returncode": 2, "stdout": "", "stderr": "no remote"})(),
            ]
            manager.validate_primary()

        push_branch.assert_not_called()
        self.assertTrue(any("kept the commit local" in message for message, _ in notices))

    def test_primary_validation_names_the_uncommitted_paths_when_autocommit_is_off(self):
        manager = GitWorktreeManager(Path("/repo"), autocommit_primary=False)
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "git_output", return_value="main"
        ), patch.object(manager, "run_git", return_value=status_process(" M changed.py\n")):
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            with self.assertRaisesRegex(GitWorktreeError, "changed.py"):
                manager.validate_primary()

    def test_primary_validation_ignores_daedalus_own_runtime_files(self):
        """The TUI writes its debug log on every launch; that must not block tasks."""
        manager = GitWorktreeManager(Path("/repo"))
        status = " M .daedalus-debug.log\n M .daedalus-debug.log.1\n?? .daedalus-memory.json\n"
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "git_output", return_value="main"
        ), patch.object(manager, "run_git", return_value=status_process(status)):
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            manager.validate_primary()

    def test_dirty_paths_keeps_real_changes_alongside_runtime_files(self):
        manager = GitWorktreeManager(Path("/repo"))
        status = " M .daedalus-debug.log\n M tui/app.py\nR  old.py -> new.py\n"
        with patch.object(manager, "run_git", return_value=status_process(status)):
            self.assertEqual(manager.dirty_paths(Path("/repo")), ["tui/app.py", "new.py"])

    def test_runtime_artifacts_are_configurable(self):
        manager = GitWorktreeManager(Path("/repo"), runtime_artifacts=(".custom-debug.log",))
        self.assertTrue(manager.is_runtime_artifact(".custom-debug.log"))
        self.assertTrue(manager.is_runtime_artifact(".custom-debug.log.2"))
        self.assertFalse(manager.is_runtime_artifact(".daedalus-debug.log"))
        self.assertFalse(manager.is_runtime_artifact(".custom-debug.log.backup"))

    def test_primary_validation_allows_other_checked_out_branch(self):
        manager = GitWorktreeManager(Path("/repo"), primary_branch="develop")
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "git_output", return_value="feature"
        ):
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            manager.validate_primary()

    def test_primary_validation_rejects_missing_target_branch(self):
        manager = GitWorktreeManager(Path("/repo"), primary_branch="missing")
        with patch("tui.git_worktree.subprocess.run") as run:
            run.return_value = type("Process", (), {"returncode": 1, "stdout": "", "stderr": ""})()
            with self.assertRaisesRegex(GitWorktreeError, "does not exist"):
                manager.validate_primary()

    def test_promote_fast_forwards_checked_out_target_with_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            worktree = Path(directory) / "task"
            worktree.mkdir()
            manager = GitWorktreeManager(repository, primary_branch="main")
            context = WorktreeContext(repository, "task-1", "base", "agent/task-task-1", worktree)
            with patch.object(manager, "_validate_primary"), patch.object(
                manager, "git_output", side_effect=["base", "tip", "main"]
            ), patch.object(manager, "run_git") as run_git, patch(
                "tui.git_worktree.subprocess.run"
            ) as run:
                run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
                manager.promote(context, "base")

            self.assertEqual(run_git.call_args.args[0], ["merge", "--ff-only", "agent/task-task-1"])

    def test_promote_updates_target_ref_when_not_checked_out(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            worktree = Path(directory) / "task"
            worktree.mkdir()
            manager = GitWorktreeManager(repository, primary_branch="develop")
            context = WorktreeContext(repository, "task-1", "base", "agent/task-task-1", worktree)
            with patch.object(manager, "_validate_primary"), patch.object(
                manager, "git_output", side_effect=["base", "tip", "feature"]
            ), patch.object(manager, "run_git") as run_git, patch(
                "tui.git_worktree.subprocess.run"
            ) as run:
                run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
                manager.promote(context, "base")

            self.assertEqual(
                run_git.call_args.args[0],
                ["update-ref", "refs/heads/develop", "tip", "base"],
            )

    def test_prepare_primary_checkout_reuses_repository_when_target_checked_out(self):
        manager = GitWorktreeManager(Path("/repo"), primary_branch="main")
        with patch.object(manager, "is_primary_checked_out", return_value=True):
            checkout, temporary = manager.prepare_primary_checkout()
        self.assertEqual(checkout, Path("/repo").resolve())
        self.assertIsNone(temporary)

    def test_prepare_primary_checkout_adds_temporary_worktree_when_needed(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            repository.mkdir()
            manager = GitWorktreeManager(repository, primary_branch="develop")
            with patch.object(manager, "is_primary_checked_out", return_value=False), patch.object(
                manager, "run_git"
            ) as run_git:
                checkout, temporary = manager.prepare_primary_checkout()

            self.assertEqual(checkout, temporary)
            self.assertEqual(checkout.parent, manager.repository.parent / manager.root_name / manager.repository.name)
            self.assertTrue(checkout.name.startswith(".graphify-"))
            self.assertEqual(run_git.call_args.args[0][:2], ["worktree", "add"])
            self.assertEqual(run_git.call_args.args[0][3], "develop")

    def test_successful_cleanup_forces_worktree_removal_before_branch_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            worktree = Path(directory) / "task"
            worktree.mkdir()
            manager = GitWorktreeManager(repository)
            context = WorktreeContext(repository, "task-1", "base", "agent/task-task-1", worktree)
            with patch.object(manager, "run_git") as run_git:
                manager.remove_successful(context)

            self.assertEqual(run_git.call_args_list[0].args[0], ["worktree", "remove", "--force", str(worktree)])
            self.assertEqual(run_git.call_args_list[1].args[0], ["branch", "-d", "agent/task-task-1"])

    def test_cancel_cleanup_force_deletes_unintegrated_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            worktree = Path(directory) / "task"
            worktree.mkdir()
            manager = GitWorktreeManager(repository)
            context = WorktreeContext(repository, "task-1", "base", "agent/task-task-1", worktree)
            with patch.object(manager, "run_git") as run_git:
                manager.remove_cancelled(context)

            self.assertEqual(run_git.call_args_list[0].args[0], ["worktree", "remove", "--force", str(worktree)])
            self.assertEqual(run_git.call_args_list[1].args[0], ["branch", "-D", "agent/task-task-1"])

    def test_discard_graphify_changes_restores_and_cleans_only_graph_output(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            (repository / "graphify-out").mkdir(parents=True)
            manager = GitWorktreeManager(repository)
            with patch.object(manager, "run_git") as run_git:
                manager.discard_graphify_changes(repository)

            self.assertEqual(
                [call.args[0] for call in run_git.call_args_list],
                [
                    ["restore", "--source=HEAD", "--staged", "--worktree", "--", "graphify-out"],
                    ["clean", "-fd", "--", "graphify-out"],
                ],
            )

    def test_stage_changes_stages_the_worktree_without_runtime_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = GitWorktreeManager(Path(directory) / "repo", runtime_artifacts=(".daedalus-orchestration",))
            worktree = Path(directory) / "task"
            with patch.object(manager, "run_git") as run_git:
                manager.stage_changes(worktree)

            run_git.assert_called_once_with(
                [
                    "add",
                    "-A",
                    "--",
                    ".",
                    ":(exclude).daedalus-orchestration",
                    ":(exclude,glob).daedalus-orchestration.[0-9]*",
                ],
                worktree,
            )

    def test_stage_changes_leaves_the_card_directory_untracked_in_a_real_repository(self):
        """The pathspec exclusions are load-bearing, so check them against real git."""
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            (repository / "sub").mkdir(parents=True)
            (repository / ".daedalus-orchestration").mkdir()
            (repository / "sub" / "a.py").write_text("a\n", encoding="utf-8")
            (repository / ".daedalus-orchestration" / "task.md").write_text("# t1\n", encoding="utf-8")
            (repository / ".daedalus-debug.log.1").write_text("log\n", encoding="utf-8")
            manager = GitWorktreeManager(repository)
            manager.run_git(["init", "-q", "."], repository)

            manager.stage_changes(repository)

            staged = manager.git_output(["diff", "--cached", "--name-only"], repository).splitlines()
            self.assertEqual(staged, ["sub/a.py"])

    def test_orchestrate_card_directory_is_a_runtime_artifact(self):
        """Orchestrate Mode's card directory must never be staged or committed."""
        manager = GitWorktreeManager(Path("/repo"))
        self.assertTrue(manager.is_runtime_artifact(".daedalus-orchestration"))
        # `git status --porcelain` reports an untracked directory with a
        # trailing slash and a tracked change inside it with the prefix.
        self.assertTrue(manager.is_runtime_artifact(".daedalus-orchestration/"))
        self.assertTrue(manager.is_runtime_artifact(".daedalus-orchestration/task.md"))
        self.assertFalse(manager.is_runtime_artifact(".daedalus-orchestration-notes.md"))

    def test_dirty_paths_ignores_the_orchestrate_card_directory(self):
        manager = GitWorktreeManager(Path("/repo"))
        status = "?? .daedalus-orchestration/\n M tui/app.py\n"
        with patch.object(manager, "run_git", return_value=status_process(status)):
            self.assertEqual(manager.dirty_paths(Path("/repo")), ["tui/app.py"])

    @patch("tui.git_worktree.subprocess.run")
    def test_provision_runs_install_and_links_readonly_path(self, run):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            worktree = Path(directory) / "task"
            repository.mkdir()
            worktree.mkdir()
            (repository / "food-data").mkdir()
            context = WorktreeContext(repository, "task-1", "base", "agent/task-task-1", worktree)
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            manager = GitWorktreeManager(repository)

            manager.provision_worktree(
                context,
                ProjectWorktreeSettings(("npm", "ci"), ("food-data",)),
            )

            self.assertTrue((worktree / "food-data").is_symlink())
            self.assertEqual((worktree / "food-data").resolve(), (repository / "food-data").resolve())
            run.assert_called_once_with(["npm", "ci"], cwd=worktree, capture_output=True, text=True)

    def test_provision_rejects_missing_readonly_path(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            worktree = Path(directory) / "task"
            repository.mkdir()
            worktree.mkdir()
            context = WorktreeContext(repository, "task-1", "base", "agent/task-task-1", worktree)
            manager = GitWorktreeManager(repository)

            with self.assertRaises(GitWorktreeError):
                manager.provision_worktree(context, ProjectWorktreeSettings(readonly_paths=("food-data",)))

    def test_provision_reuses_existing_correct_readonly_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            worktree = Path(directory) / "task"
            repository.mkdir()
            worktree.mkdir()
            source = repository / "food-data"
            source.mkdir()
            target = worktree / "food-data"
            target.symlink_to(source, target_is_directory=True)
            context = WorktreeContext(repository, "task-1", "base", "agent/task-task-1", worktree)
            manager = GitWorktreeManager(repository)

            manager.provision_worktree(context, ProjectWorktreeSettings(readonly_paths=("food-data",)))

            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), source.resolve())

    def test_provision_rejects_existing_real_readonly_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            worktree = Path(directory) / "task"
            repository.mkdir()
            worktree.mkdir()
            (repository / "food-data").mkdir()
            (worktree / "food-data").mkdir()
            context = WorktreeContext(repository, "task-1", "base", "agent/task-task-1", worktree)
            manager = GitWorktreeManager(repository)

            with self.assertRaisesRegex(GitWorktreeError, "destination exists"):
                manager.provision_worktree(context, ProjectWorktreeSettings(readonly_paths=("food-data",)))

    def test_remote_exists_checks_origin_url(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "git@example.com:repo.git\n", "stderr": ""})()
            from tui.git_worktree import remote_exists

            self.assertTrue(remote_exists(Path("/repo")))
            self.assertEqual(run.call_args.args[0], ["git", "remote", "get-url", "origin"])

    def test_remote_exists_false_when_missing(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.return_value = type("Process", (), {"returncode": 2, "stdout": "", "stderr": "error"})()
            from tui.git_worktree import remote_exists

            self.assertFalse(remote_exists(Path("/repo"), remote="upstream"))

    def test_push_branch_runs_push_with_upstream(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.side_effect = [
                type("Process", (), {"returncode": 0, "stdout": "git@example.com:repo.git\n", "stderr": ""})(),
                type("Process", (), {"returncode": 0, "stdout": "a" * 40 + "\n", "stderr": ""})(),
                type("Process", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})(),
            ]
            from tui.git_worktree import push_branch

            self.assertEqual(push_branch(Path("/repo"), "james"), "a" * 40)
            self.assertEqual(
                [call.args[0] for call in run.call_args_list],
                [
                    ["git", "remote", "get-url", "origin"],
                    ["git", "rev-parse", "--verify", "--quiet", "refs/heads/james"],
                    ["git", "push", "-u", "origin", "james"],
                ],
            )

    def test_push_primary_notice_names_the_pushed_commit(self):
        notices: list[tuple[str, str]] = []
        manager = GitWorktreeManager(
            Path("/repo"),
            on_notice=lambda message, kind="status": notices.append((message, kind)),
        )
        with patch("tui.git_worktree.remote_exists", return_value=True), patch(
            "tui.git_worktree.push_branch", return_value="a" * 40
        ):
            self.assertTrue(manager.push_primary())

        self.assertEqual(
            notices,
            [(f"Pushed main to origin (commit {'a' * 40}).", "pushed")],
        )

    def test_push_branch_rejects_missing_remote(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.return_value = type("Process", (), {"returncode": 2, "stdout": "", "stderr": "missing"})()
            from tui.git_worktree import push_branch

            with self.assertRaisesRegex(GitWorktreeError, "not configured"):
                push_branch(Path("/repo"), "main")

    def test_push_branch_rejects_blank_branch(self):
        from tui.git_worktree import push_branch

        with self.assertRaisesRegex(GitWorktreeError, "empty"):
            push_branch(Path("/repo"), "  ")

    def test_push_branch_surfaces_auth_failure(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.side_effect = [
                type("Process", (), {"returncode": 0, "stdout": "git@example.com:repo.git\n", "stderr": ""})(),
                type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("Process", (), {"returncode": 128, "stdout": "", "stderr": "Authentication failed"})(),
            ]
            from tui.git_worktree import push_branch

            with self.assertRaisesRegex(GitWorktreeError, "Authentication failed"):
                push_branch(Path("/repo"), "main")


if __name__ == "__main__":
    unittest.main()
