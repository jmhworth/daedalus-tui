import unittest
import tempfile
from pathlib import Path
from unittest.mock import call, patch

from tui.git_worktree import GitWorktreeError, GitWorktreeManager, WorktreeContext
from tui.project_config import ProjectWorktreeSettings


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
            with patch.object(manager, "validate_primary", return_value=False), patch.object(manager, "git_output", return_value="abc123"), patch.object(manager, "run_git") as run_git:
                context = manager.create("task-1")

            self.assertEqual(context.base_commit, "abc123")
            self.assertEqual(context.branch_name, "agent/task-task-1")
            self.assertEqual(context.path, Path(directory).resolve() / ".daedalus-worktrees" / "repo" / "task-task-1")
            self.assertEqual(run_git.call_args.args[0][:4], ["worktree", "add", "-b", "agent/task-task-1"])

    def test_primary_validation_rejects_dirty_repository_when_target_checked_out(self):
        manager = GitWorktreeManager(Path("/repo"))
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "git_output", side_effect=["main", " M changed.py"]
        ):
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            with self.assertRaises(GitWorktreeError):
                manager._validate_primary()

    def test_primary_validation_auto_commits_dirty_repository_when_requested(self):
        manager = GitWorktreeManager(Path("/repo"))
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "is_primary_checked_out", return_value=True
        ), patch.object(manager, "is_clean", side_effect=[False, True]), patch.object(
            manager, "commit_changes", return_value=True
        ) as commit_changes:
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            committed = manager.validate_primary(auto_commit_dirty=True)

        self.assertTrue(committed)
        commit_changes.assert_called_once_with(
            Path("/repo").resolve(),
            "Daedalus: auto-commit dirty primary before starting agent",
        )

    def test_primary_validation_still_rejects_when_auto_commit_leaves_dirt(self):
        manager = GitWorktreeManager(Path("/repo"))
        with patch("tui.git_worktree.subprocess.run") as run, patch.object(
            manager, "is_primary_checked_out", return_value=True
        ), patch.object(manager, "is_clean", return_value=False), patch.object(
            manager, "commit_changes", return_value=False
        ):
            run.return_value = type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            with self.assertRaisesRegex(GitWorktreeError, "must be clean"):
                manager.validate_primary(auto_commit_dirty=True)

    def test_create_auto_commits_dirty_primary_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = GitWorktreeManager(Path(directory) / "repo")
            with patch.object(
                manager, "validate_primary", return_value=True
            ) as validate_primary, patch.object(
                manager, "git_output", return_value="abc123"
            ), patch.object(manager, "run_git") as run_git:
                context = manager.create("task-1")

            validate_primary.assert_called_once_with(auto_commit_dirty=True)
            self.assertEqual(context.base_commit, "abc123")
            self.assertEqual(run_git.call_args.args[0][:4], ["worktree", "add", "-b", "agent/task-task-1"])

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

    def test_stage_changes_stages_the_entire_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = GitWorktreeManager(Path(directory) / "repo")
            worktree = Path(directory) / "task"
            with patch.object(manager, "run_git") as run_git:
                manager.stage_changes(worktree)

            run_git.assert_called_once_with(["add", "-A"], worktree)

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
                type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("Process", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})(),
            ]
            from tui.git_worktree import push_branch

            push_branch(Path("/repo"), "james", pull_first=False)
            self.assertEqual(
                [call.args[0] for call in run.call_args_list],
                [
                    ["git", "remote", "get-url", "origin"],
                    ["git", "rev-parse", "--verify", "--quiet", "refs/heads/james"],
                    ["git", "push", "-u", "origin", "james"],
                ],
            )

    def test_push_branch_pulls_before_push_by_default(self):
        with patch("tui.git_worktree.pull_branch") as pull, patch("tui.git_worktree.subprocess.run") as run:
            run.side_effect = [
                type("Process", (), {"returncode": 0, "stdout": "git@example.com:repo.git\n", "stderr": ""})(),
                type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("Process", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})(),
            ]
            from tui.git_worktree import push_branch

            push_branch(Path("/repo"), "james")
            pull.assert_called_once_with(Path("/repo"), "james", "origin")
            self.assertEqual(run.call_args_list[-1].args[0], ["git", "push", "-u", "origin", "james"])

    def test_pull_branch_fast_forwards_unchecked_branch(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.side_effect = [
                type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # fetch
                type("Process", (), {"returncode": 0, "stdout": "aaa\n", "stderr": ""})(),  # local tip
                type("Process", (), {"returncode": 0, "stdout": "bbb\n", "stderr": ""})(),  # remote tip
                type("Process", (), {"returncode": 1, "stdout": "", "stderr": ""})(),  # remote not ancestor of local
                type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # worktree list empty
                type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # local is ancestor of remote
                type("Process", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # update-ref
            ]
            from tui.git_worktree import pull_branch

            pull_branch(Path("/repo"), "main")
            self.assertEqual(
                run.call_args_list[-1].args[0],
                ["git", "update-ref", "refs/heads/main", "bbb"],
            )

    def test_pull_branch_ignores_missing_remote_branch(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.return_value = type(
                "Process",
                (),
                {"returncode": 1, "stdout": "", "stderr": "fatal: couldn't find remote ref main"},
            )()
            from tui.git_worktree import pull_branch

            pull_branch(Path("/repo"), "main")
            self.assertEqual(
                run.call_args.args[0],
                ["git", "fetch", "origin", "refs/heads/main:refs/remotes/origin/main"],
            )

    def test_push_branch_rejects_missing_remote(self):
        with patch("tui.git_worktree.subprocess.run") as run:
            run.return_value = type("Process", (), {"returncode": 2, "stdout": "", "stderr": "missing"})()
            from tui.git_worktree import push_branch

            with self.assertRaisesRegex(GitWorktreeError, "not configured"):
                push_branch(Path("/repo"), "main", pull_first=False)

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
                push_branch(Path("/repo"), "main", pull_first=False)

    def _init_repo(self, path: Path) -> None:
        import subprocess

        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True)

    def _commit_file(self, path: Path, relative: str, content: str, message: str) -> None:
        import subprocess

        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", relative], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", message], cwd=path, check=True, capture_output=True)

    def test_pull_branch_conflict_preserves_isolated_worktree(self):
        import subprocess

        from tui.git_worktree import SyncMergeConflictError, list_unmerged_paths, pull_branch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            local = root / "local"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            self._init_repo(local)
            self._commit_file(local, "shared.txt", "base\n", "base")
            subprocess.run(
                ["git", "remote", "add", "origin", str(remote)],
                cwd=local,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=local, check=True, capture_output=True)

            other = root / "other"
            subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            self._commit_file(other, "shared.txt", "remote\n", "remote change")
            subprocess.run(["git", "push", "origin", "main"], cwd=other, check=True, capture_output=True)

            self._commit_file(local, "shared.txt", "local\n", "local change")
            with self.assertRaises(SyncMergeConflictError) as raised:
                pull_branch(local, "main")
            error = raised.exception
            self.assertTrue(error.worktree_path.exists())
            self.assertIn("shared.txt", error.conflicted_paths)
            self.assertTrue(list_unmerged_paths(error.worktree_path))
            # Primary still has main checked out, so recovery attaches via temp branch.
            self.assertTrue(error.used_temp_branch)
            # Operating checkout must not be mid-merge.
            porcelain = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=local,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertNotIn("UU", porcelain)

    def test_pull_branch_uses_temp_branch_when_operating_checkout_exists(self):
        import subprocess

        from tui.git_worktree import SyncMergeConflictError, pull_branch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            local = root / "local"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            self._init_repo(local)
            self._commit_file(local, "shared.txt", "base\n", "base")
            subprocess.run(
                ["git", "remote", "add", "origin", str(remote)],
                cwd=local,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=local, check=True, capture_output=True)

            other = root / "other"
            subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            self._commit_file(other, "shared.txt", "remote\n", "remote change")
            subprocess.run(["git", "push", "origin", "main"], cwd=other, check=True, capture_output=True)
            self._commit_file(local, "shared.txt", "local\n", "local change")

            # Keep main checked out in primary so sync must use a temp branch.
            current = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=local,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(current, "main")
            with self.assertRaises(SyncMergeConflictError) as raised:
                pull_branch(local, "main")
            error = raised.exception
            self.assertTrue(error.used_temp_branch)
            self.assertIsNotNone(error.temp_branch_name)
            self.assertTrue(str(error.temp_branch_name).startswith("daedalus/sync-resolve-"))
            self.assertTrue(error.worktree_path.name.startswith(".sync-resolve-"))
            self.assertEqual(
                subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=local,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                "main",
            )

    def test_finalize_and_abort_sync_merge(self):
        import subprocess

        from tui.git_worktree import (
            SyncMergeConflictError,
            abort_sync_merge,
            finalize_sync_merge,
            pull_branch,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            local = root / "local"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            self._init_repo(local)
            self._commit_file(local, "shared.txt", "base\n", "base")
            subprocess.run(
                ["git", "remote", "add", "origin", str(remote)],
                cwd=local,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=local, check=True, capture_output=True)

            other = root / "other"
            subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            self._commit_file(other, "shared.txt", "remote\n", "remote change")
            subprocess.run(["git", "push", "origin", "main"], cwd=other, check=True, capture_output=True)
            self._commit_file(local, "shared.txt", "local\n", "local change")

            with self.assertRaises(SyncMergeConflictError) as raised:
                pull_branch(local, "main")
            conflict = raised.exception
            (conflict.worktree_path / "shared.txt").write_text("resolved\n", encoding="utf-8")
            tip_before = subprocess.run(
                ["git", "rev-parse", "refs/heads/main"],
                cwd=local,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            finalize_sync_merge(
                local,
                conflict.worktree_path,
                "main",
                used_temp_branch=conflict.used_temp_branch,
                temp_branch_name=conflict.temp_branch_name,
            )
            tip_after = subprocess.run(
                ["git", "rev-parse", "refs/heads/main"],
                cwd=local,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertNotEqual(tip_before, tip_after)
            self.assertFalse(conflict.worktree_path.exists())

            # Abort path for a fresh conflict.
            self._commit_file(local, "shared.txt", "local2\n", "local2")
            self._commit_file(other, "shared.txt", "remote2\n", "remote2")
            subprocess.run(["git", "push", "origin", "main"], cwd=other, check=True, capture_output=True)
            with self.assertRaises(SyncMergeConflictError) as raised_again:
                pull_branch(local, "main")
            second = raised_again.exception
            abort_sync_merge(local, second.worktree_path, temp_branch_name=second.temp_branch_name)
            self.assertFalse(second.worktree_path.exists())

    def test_successful_pull_removes_temp_worktree(self):
        import subprocess

        from tui.git_worktree import pull_branch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            local = root / "local"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            self._init_repo(local)
            self._commit_file(local, "file.txt", "base\n", "base")
            subprocess.run(
                ["git", "remote", "add", "origin", str(remote)],
                cwd=local,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=local, check=True, capture_output=True)

            other = root / "other"
            subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            self._commit_file(other, "remote-only.txt", "ok\n", "remote only")
            subprocess.run(["git", "push", "origin", "main"], cwd=other, check=True, capture_output=True)

            # Diverged non-conflicting histories force a merge worktree (not update-ref).
            self._commit_file(local, "local-only.txt", "ok\n", "local only")
            subprocess.run(["git", "checkout", "--detach"], cwd=local, check=True, capture_output=True)
            pull_branch(local, "main")
            worktree_root = local.parent / ".daedalus-worktrees" / local.name
            leftovers = list(worktree_root.glob(".sync-*")) if worktree_root.exists() else []
            self.assertEqual(leftovers, [])
            tip = subprocess.run(
                ["git", "rev-parse", "refs/heads/main"],
                cwd=local,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            remote_tip = subprocess.run(
                ["git", "rev-parse", "refs/remotes/origin/main"],
                cwd=local,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            # Local tip advanced past remote via merge commit.
            self.assertNotEqual(tip, remote_tip)
            contains = subprocess.run(
                ["git", "merge-base", "--is-ancestor", remote_tip, tip],
                cwd=local,
                capture_output=True,
            )
            self.assertEqual(contains.returncode, 0)

    def test_free_branch_sync_worktree_checks_out_operating_branch(self):
        import subprocess

        from tui.git_worktree import SyncMergeConflictError, pull_branch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            local = root / "local"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            self._init_repo(local)
            self._commit_file(local, "shared.txt", "base\n", "base")
            subprocess.run(
                ["git", "remote", "add", "origin", str(remote)],
                cwd=local,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=local, check=True, capture_output=True)

            other = root / "other"
            subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=other,
                check=True,
                capture_output=True,
            )
            self._commit_file(other, "shared.txt", "remote\n", "remote change")
            subprocess.run(["git", "push", "origin", "main"], cwd=other, check=True, capture_output=True)
            self._commit_file(local, "shared.txt", "local\n", "local change")
            subprocess.run(["git", "checkout", "--detach"], cwd=local, check=True, capture_output=True)

            with self.assertRaises(SyncMergeConflictError) as raised:
                pull_branch(local, "main")
            error = raised.exception
            self.assertFalse(error.used_temp_branch)
            self.assertIsNone(error.temp_branch_name)
            self.assertTrue(error.worktree_path.name.startswith(".sync-pull-"))
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=error.worktree_path,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(branch, "main")
