import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from tui.agent_runner import AgentResult
from tui.git_worktree import GitWorktreeError, WorktreeContext
from tui.graphify import GraphifyResult
from tui.orchestrator import (
    BUNDLED_PROFILE_ROOT,
    LocalOrchestrator,
    OrchestrationSettings,
    task_commit_subject,
)
from tui.firebase import DeployResult, FirebaseStatus
from tui.supabase_migrations import PushResult
from tui.verification import VerificationResult


class OrchestratorTests(unittest.TestCase):
    def test_task_commit_subject_uses_the_task_goal_and_formats_the_title(self):
        self.assertEqual(
            task_commit_subject("ignored generated implementation prompt", "task-1", "Fix login validation"),
            "Daedalus: Fix login validation",
        )
        self.assertEqual(
            task_commit_subject("# Add the account settings screen\nDetailed requirements follow.", "task-1"),
            "Daedalus: Add the account settings screen",
        )

    def test_plan_waits_for_questions_and_preserves_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "plan", tokens_consumed=12)
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            (context.path / ".agents" / "profiles").mkdir(parents=True)
            (context.path / ".agents" / "profiles" / "planning.md").write_text(
                "PLANNING_PROFILE_FROM_WORKTREE", encoding="utf-8"
            )
            manager = Mock()
            manager.create.return_value = context
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda _phase, _message, _channel: None,
            )

            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager):
                result = orchestrator.run("Make a plan", "codex", "luna", "high", mode="plan")

        self.assertTrue(result.succeeded)
        self.assertTrue(result.awaiting_plan)
        self.assertEqual(result.tokens_consumed, 12)
        manager.remove_successful.assert_not_called()
        manager.discard_graphify_changes.assert_called_once_with(context.path)
        manager.reset_task_to_base.assert_called_once_with(context)
        self.assertIn("PLANNING_PROFILE_FROM_WORKTREE", runner.run.call_args.args[0].prompt)

    def test_missing_profile_falls_back_to_the_bundled_profile(self):
        """Projects opened by path have no .agents/; Daedalus' own profile still applies."""
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "plan")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )

            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager):
                result = orchestrator.run("Make a plan", "codex", "luna", "high", mode="plan")

        self.assertTrue(result.succeeded)
        self.assertTrue(result.awaiting_plan)
        profile_events = [(message, channel) for phase, message, channel in events if phase == "profile"]
        self.assertEqual([channel for _, channel in profile_events], ["status"])
        self.assertIn("bundled plan profile", profile_events[0][0])
        bundled = (BUNDLED_PROFILE_ROOT / "planning.md").read_text(encoding="utf-8")
        self.assertIn(bundled.strip(), runner.run.call_args.args[0].prompt)
        self.assertNotIn(".agents/profiles", runner.run.call_args.args[0].prompt)

    def test_missing_profile_is_reported_when_no_bundled_fallback_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "plan")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )

            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager), patch(
                "tui.orchestrator.BUNDLED_PROFILE_ROOT", repository / "no-bundled-profiles"
            ):
                result = orchestrator.run("Make a plan", "codex", "luna", "high", mode="plan")

        self.assertTrue(result.succeeded)
        self.assertTrue(result.awaiting_plan)
        self.assertTrue(any(phase == "profile" and channel == "error" for phase, _, channel in events))
        self.assertNotIn("BEGIN_DAEDALUS_PROFILE", runner.run.call_args.args[0].prompt)

    def test_agent_requests_allowlist_the_discovered_verification_commands(self):
        """Claude runs non-interactively, so its own checks must be pre-approved."""
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            worktree = repository / "worktree"
            (worktree / "tests").mkdir(parents=True)
            (worktree / "package.json").write_text('{"scripts": {"test": "vitest run"}}', encoding="utf-8")
            runner = Mock()
            runner.run.return_value = AgentResult("claude", 0, "done")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", worktree)
            manager = Mock()
            orchestrator = LocalOrchestrator(repository, runner, OrchestrationSettings(), lambda *_: None)

            with patch("tui.orchestrator.discover_commands", return_value=[
                ["npm", "test"],
                ["/opt/venv/bin/python3", "-m", "pytest"],
            ]):
                orchestrator.run_agent(manager, context, ("claude", "claude-opus-5", "high"), "Do it")

        request = runner.run.call_args.args[0]
        self.assertEqual(
            request.allowed_tools,
            ("Bash(npm test:*)", "Bash(/opt/venv/bin/python3 -m pytest:*)", "Bash(python3 -m pytest:*)"),
        )

    def test_agent_requests_skip_discovery_for_a_missing_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("claude", 0, "done")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "missing")
            orchestrator = LocalOrchestrator(repository, runner, OrchestrationSettings(), lambda *_: None)

            orchestrator.run_agent(Mock(), context, ("claude", "claude-opus-5", "high"), "Do it")

        self.assertEqual(runner.run.call_args.args[0].allowed_tools, ())

    def test_planning_followup_uses_the_planning_profile_through_task_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "updated plan")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            (context.path / ".agents" / "profiles").mkdir(parents=True)
            (context.path / ".agents" / "profiles" / "planning.md").write_text(
                "PLANNING_PROFILE_FOR_FOLLOWUP", encoding="utf-8"
            )
            manager = Mock()
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda _phase, _message, _channel: None,
            )

            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager):
                result = orchestrator.run(
                    "Re-evaluate the plan using the user's answers.",
                    "codex",
                    "luna",
                    "high",
                    mode="plan",
                    existing_context=context,
                )

        self.assertTrue(result.succeeded)
        self.assertIn("PLANNING_PROFILE_FOR_FOLLOWUP", runner.run.call_args.args[0].prompt)

    def test_failed_plan_does_not_report_agent_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 1, "", "plan failed", tokens_consumed=12)
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda _phase, _message, _channel: None,
            )

            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager):
                result = orchestrator.run("Make a plan", "codex", "luna", "high", mode="plan")

        self.assertFalse(result.succeeded)
        self.assertEqual(result.tokens_consumed, 0)

    def test_graphify_failure_is_reported_without_failing_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "graphify-out").mkdir()
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                Mock(),
                OrchestrationSettings(),
                lambda phase, message, channel="status": events.append((phase, message, channel)),
            )
            manager = Mock()
            manager.prepare_primary_checkout.return_value = (repository.resolve(), None)
            manager.discard_graphify_changes = Mock()
            with patch(
                "tui.orchestrator.update_repository",
                return_value=GraphifyResult(True, False, "Operation not permitted"),
            ):
                orchestrator.refresh_graphify(manager, "task-1")

        manager.commit_graphify_changes.assert_not_called()
        manager.discard_graphify_changes.assert_called_once_with(repository.resolve())
        manager.cleanup_temporary_checkout.assert_called_once_with(None)
        self.assertTrue(any(phase == "graphify" and "Operation not permitted" in message for phase, message, _ in events))

    def test_successful_graphify_changes_are_committed_after_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "graphify-out").mkdir()
            orchestrator = LocalOrchestrator(repository, Mock(), OrchestrationSettings(), lambda *_: None)
            manager = Mock()
            manager.prepare_primary_checkout.return_value = (repository.resolve(), None)
            manager.commit_graphify_changes.return_value = True
            with patch(
                "tui.orchestrator.update_repository",
                return_value=GraphifyResult(True, True, "updated"),
            ):
                orchestrator.refresh_graphify(manager, "task-1")

        manager.commit_graphify_changes.assert_called_once_with(
            "Daedalus: Task 1 (graphify update)",
            repository.resolve(),
        )
        manager.discard_graphify_changes.assert_not_called()
        manager.cleanup_temporary_checkout.assert_called_once_with(None)

    def test_merge_failure_deploys_resolver_and_retries_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            (repository / "worktree" / ".agents" / "profiles").mkdir(parents=True)
            (repository / "worktree" / ".agents" / "profiles" / "coding.md").write_text(
                "CODING_PROFILE_FOR_INITIAL", encoding="utf-8"
            )
            (repository / "worktree" / ".agents" / "profiles" / "integrating.md").write_text(
                "INTEGRATING_PROFILE_FOR_RESOLVER", encoding="utf-8"
            )
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(verification_commands=(("true",),), resolver_attempt_limit=2),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "changed"
            manager.has_unmerged_paths.return_value = False
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", side_effect=[VerificationResult(True, ""), VerificationResult(True, ""), VerificationResult(True, "")]),
                patch.object(orchestrator, "integrate", wraps=orchestrator.integrate) as integrate,
            ):
                manager.merge_primary_into_task.side_effect = GitWorktreeError("merge conflict")
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium")

        self.assertTrue(result.succeeded)
        self.assertTrue(any(phase == "resolving" for phase, _, _ in events))
        self.assertGreaterEqual(runner.run.call_count, 2)
        manager.commit_changes.assert_any_call(context.path, "Daedalus: Build it")
        manager.commit_changes.assert_any_call(
            context.path,
            "Daedalus: Build it (integration resolver 1)",
        )
        integrate.assert_called_once()
        manager.stage_changes.assert_called_once_with(context.path)
        stage_call = call.stage_changes(context.path)
        unmerged_call = call.has_unmerged_paths(context.path)
        self.assertLess(manager.method_calls.index(stage_call), manager.method_calls.index(unmerged_call))
        manager.promote.assert_called_once()
        manager.remove_successful.assert_called_once()
        self.assertIn("CODING_PROFILE_FOR_INITIAL", runner.run.call_args_list[0].args[0].prompt)
        self.assertIn("INTEGRATING_PROFILE_FOR_RESOLVER", runner.run.call_args_list[1].args[0].prompt)

    def test_failed_resolver_preserves_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.side_effect = [
                AgentResult("codex", 0, "done"),
                AgentResult("codex", 1, "", "resolver failed"),
            ]
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "changed"
            manager.merge_primary_into_task.side_effect = GitWorktreeError("merge conflict")
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(verification_commands=(("true",),), resolver_attempt_limit=1),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager), patch(
                "tui.orchestrator.run_verification", return_value=VerificationResult(True, "")
            ):
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium")

        self.assertFalse(result.succeeded)
        self.assertEqual(result.worktree, context.path)
        manager.remove_successful.assert_not_called()
        self.assertTrue(any(phase == "failed" for phase, _, _ in events))

    def test_failed_task_verification_runs_repair_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            (context.path / ".agents" / "profiles").mkdir(parents=True)
            profile_path = context.path / ".agents" / "profiles" / "coding.md"
            profile_path.write_text(
                "CODING_PROFILE_FOR_INITIAL_AND_REPAIR", encoding="utf-8"
            )

            def run_agent(request, _on_event):
                if "CODING_PROFILE_FOR_INITIAL" in request.prompt:
                    profile_path.write_text("CODING_PROFILE_FOR_REPAIR", encoding="utf-8")
                    return AgentResult("codex", 0, "done", tokens_consumed=10)
                return AgentResult("codex", 0, "repaired", tokens_consumed=5)

            runner.run.side_effect = run_agent
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "changed"
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(verification_commands=(("true",),), task_verification_attempt_limit=2),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", side_effect=[
                    VerificationResult(False, "tests failed"),
                    VerificationResult(True, ""),
                    VerificationResult(True, ""),
                ]),
            ):
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium")

        self.assertTrue(result.succeeded)
        self.assertEqual(runner.run.call_count, 2)
        self.assertEqual(result.tokens_consumed, 15)
        self.assertTrue(any(phase == "repairing" for phase, _, _ in events))
        self.assertIn("CODING_PROFILE_FOR_INITIAL_AND_REPAIR", runner.run.call_args_list[0].args[0].prompt)
        self.assertIn("CODING_PROFILE_FOR_REPAIR", runner.run.call_args_list[1].args[0].prompt)
        manager.commit_changes.assert_any_call(context.path, "Daedalus: Build it")
        manager.commit_changes.assert_any_call(
            context.path,
            "Daedalus: Build it (verification repair 1)",
        )

    def test_exhausted_verification_logs_each_failure_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.side_effect = [
                AgentResult("codex", 0, "done"),
                AgentResult("codex", 0, "repair-1"),
                AgentResult("codex", 0, "repair-2"),
            ]
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "changed"
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(verification_commands=(("true",),), task_verification_attempt_limit=3),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch(
                    "tui.orchestrator.run_verification",
                    side_effect=[
                        VerificationResult(False, "first suite failed"),
                        VerificationResult(False, "second suite failed"),
                        VerificationResult(False, "third suite failed"),
                    ],
                ),
            ):
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium")

        self.assertFalse(result.succeeded)
        self.assertIn("first suite failed", result.error)
        self.assertIn("second suite failed", result.error)
        self.assertIn("third suite failed", result.error)
        verification_errors = [
            message for phase, message, channel in events if phase == "verification" and channel == "error"
        ]
        self.assertEqual(len(verification_errors), 3)
        self.assertTrue(any("first suite failed" in message for message in verification_errors))
        failed_events = [message for phase, message, channel in events if phase == "failed" and channel == "error"]
        self.assertEqual(len(failed_events), 1)
        self.assertIn("Verification failed after 3 attempts", failed_events[0])
        self.assertIn("third suite failed", failed_events[0])
        manager.remove_successful.assert_not_called()

    def test_integration_resume_skips_coding_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(verification_commands=(("true",),)),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")) as verify,
            ):
                result = orchestrator.run(
                    "Build it",
                    "codex",
                    "gpt-5.6-luna",
                    "medium",
                    existing_context=context,
                    resume_from="integration",
                )

        self.assertTrue(result.succeeded)
        runner.run.assert_not_called()
        manager.commit_changes.assert_not_called()
        manager.merge_primary_into_task.assert_called_once_with(context)
        verify.assert_called_once()
        manager.promote.assert_called_once()
        manager.remove_successful.assert_called_once()
        self.assertTrue(any("retrying from integration" in message for phase, message, _ in events if phase == "ready"))

    def test_cancelled_agent_removes_unintegrated_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", -15, "", stopped_reason="cancelled")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager):
                from tui.agent_runner import AgentControl
                control = AgentControl()
                control.request_cancel()
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium", control=control)

        self.assertFalse(result.succeeded)
        self.assertTrue(result.cancelled)
        manager.remove_cancelled.assert_called_once_with(context)
        self.assertTrue(any(phase == "cancelled" for phase, _, _ in events))

    def test_tagged_topic_is_embedded_from_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "answer")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            topic_dir = context.path / "topic_files"
            topic_dir.mkdir(parents=True)
            (topic_dir / "mvp.md").write_text(
                "# MVP\n\n## Topic Goal\nShip it.\n\n## Topic Status\nopen\n\n## State Log\n",
                encoding="utf-8",
            )
            manager = Mock()
            manager.create.return_value = context
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda _phase, _message, _channel: None,
            )

            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager):
                result = orchestrator.run(
                    "Explain the MVP",
                    "codex",
                    "luna",
                    "high",
                    mode="ask",
                    topic_slug="mvp",
                )

        self.assertTrue(result.succeeded)
        prompt = runner.run.call_args.args[0].prompt
        self.assertIn("BEGIN_DAEDALUS_TOPIC", prompt)
        self.assertIn("Ship it.", prompt)
        self.assertIn("read-only for topic files", prompt)

    def test_missing_topic_is_reported_without_embedding(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "answer")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )

            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager):
                result = orchestrator.run(
                    "Explain",
                    "codex",
                    "luna",
                    "high",
                    mode="ask",
                    topic_slug="missing",
                )

        self.assertTrue(result.succeeded)
        self.assertTrue(any(phase == "topic" and channel == "error" for phase, _, channel in events))
        self.assertNotIn("BEGIN_DAEDALUS_TOPIC", runner.run.call_args.args[0].prompt)

    def test_migration_push_skipped_when_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "changed"
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(
                    verification_commands=(("true",),),
                    supabase_db_push_enabled=False,
                ),
                lambda *_: None,
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch("tui.orchestrator.migrations_pending", return_value=True) as pending,
                patch("tui.orchestrator.push_migrations") as push,
            ):
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium")

        self.assertTrue(result.succeeded)
        pending.assert_not_called()
        push.assert_not_called()

    def test_migration_push_skipped_when_no_migration_diff(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "changed"
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(verification_commands=(("true",),)),
                lambda *_: None,
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch("tui.orchestrator.migrations_pending", return_value=False) as pending,
                patch("tui.orchestrator.push_migrations") as push,
            ):
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium")

        self.assertTrue(result.succeeded)
        pending.assert_called()
        push.assert_not_called()

    def test_migration_push_runs_once_after_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "changed"
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(verification_commands=(("true",),)),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch("tui.orchestrator.migrations_pending", return_value=True),
                patch(
                    "tui.orchestrator.push_migrations",
                    return_value=PushResult(True, "Remote database is up to date."),
                ) as push,
            ):
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium")

        self.assertTrue(result.succeeded)
        push.assert_called_once()
        self.assertEqual(push.call_args.args[0], context.path)
        self.assertTrue(any(phase == "migrations" for phase, _, _ in events))
        self.assertTrue(any(phase == "ready" for phase, _, _ in events))

    def test_migration_push_failure_repairs_then_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            (context.path / ".agents" / "profiles").mkdir(parents=True)
            (context.path / ".agents" / "profiles" / "coding.md").write_text(
                "CODING_PROFILE_FOR_MIGRATION_REPAIR", encoding="utf-8"
            )

            def run_agent(request, _on_event):
                if "Migration push failure" in request.prompt:
                    return AgentResult("codex", 0, "fixed migration", tokens_consumed=4)
                return AgentResult("codex", 0, "done", tokens_consumed=8)

            runner.run.side_effect = run_agent
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "changed"
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(
                    verification_commands=(("true",),),
                    task_verification_attempt_limit=2,
                ),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch("tui.orchestrator.migrations_pending", return_value=True),
                patch(
                    "tui.orchestrator.push_migrations",
                    side_effect=[
                        PushResult(False, "ERROR: relation already exists"),
                        PushResult(True, "Applied migration."),
                    ],
                ) as push,
            ):
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium")

        self.assertTrue(result.succeeded)
        self.assertEqual(push.call_count, 2)
        self.assertEqual(runner.run.call_count, 2)
        self.assertTrue(
            any(phase == "migrations" and channel == "error" for phase, _, channel in events)
        )
        self.assertTrue(any(phase == "repairing" for phase, _, _ in events))
        self.assertIn("Migration push failure", runner.run.call_args_list[1].args[0].prompt)
        self.assertIn("CODING_PROFILE_FOR_MIGRATION_REPAIR", runner.run.call_args_list[1].args[0].prompt)
        manager.commit_changes.assert_any_call(
            context.path,
            "Daedalus: Build it (Supabase migration repair 1)",
        )

    def test_exhausted_migration_push_logs_each_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.side_effect = [
                AgentResult("codex", 0, "done"),
                AgentResult("codex", 0, "repair-1"),
                AgentResult("codex", 0, "repair-2"),
            ]
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "changed"
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(
                    verification_commands=(("true",),),
                    task_verification_attempt_limit=3,
                ),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch("tui.orchestrator.migrations_pending", return_value=True),
                patch(
                    "tui.orchestrator.push_migrations",
                    side_effect=[
                        PushResult(False, "first migration failed"),
                        PushResult(False, "second migration failed"),
                        PushResult(False, "third migration failed"),
                    ],
                ),
            ):
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium")

        self.assertFalse(result.succeeded)
        self.assertIn("first migration failed", result.error)
        self.assertIn("second migration failed", result.error)
        self.assertIn("third migration failed", result.error)
        migration_errors = [
            message for phase, message, channel in events if phase == "migrations" and channel == "error"
        ]
        self.assertEqual(len(migration_errors), 3)
        failed_events = [message for phase, message, channel in events if phase == "failed" and channel == "error"]
        self.assertEqual(len(failed_events), 1)
        self.assertIn("Migration push failed after 3 attempts", failed_events[0])
        manager.remove_successful.assert_not_called()
        manager.promote.assert_not_called()

    def _firebase_orchestrator(self, repository, runner, events=None, **settings):
        context = WorktreeContext(
            repository, "task", "base", "agent/task-task", repository / "worktree"
        )
        manager = Mock()
        manager.create.return_value = context
        manager.head.return_value = "changed"
        orchestrator = LocalOrchestrator(
            repository,
            runner,
            OrchestrationSettings(verification_commands=(("true",),), **settings),
            (lambda phase, message, channel: events.append((phase, message, channel)))
            if events is not None
            else (lambda *_: None),
        )
        return orchestrator, manager, context

    def test_firebase_deploy_skipped_when_the_project_is_not_registered(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            orchestrator, manager, _ = self._firebase_orchestrator(repository, runner)
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch(
                    "tui.orchestrator.load_firebase_status",
                    return_value=FirebaseStatus(registered=False),
                ),
                patch("tui.orchestrator.firebase_changes_pending") as pending,
                patch("tui.orchestrator.deploy_firebase") as deploy,
            ):
                result = orchestrator.run("Build it", "codex", "gpt-6-astra", "medium")

        self.assertTrue(result.succeeded)
        pending.assert_not_called()
        deploy.assert_not_called()

    def test_firebase_deploy_skipped_when_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            orchestrator, manager, _ = self._firebase_orchestrator(
                repository, runner, firebase_deploy_enabled=False
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch(
                    "tui.orchestrator.load_firebase_status",
                    return_value=FirebaseStatus(True, "demo-app"),
                ) as status,
                patch("tui.orchestrator.deploy_firebase") as deploy,
            ):
                result = orchestrator.run("Build it", "codex", "gpt-6-astra", "medium")

        self.assertTrue(result.succeeded)
        status.assert_not_called()
        deploy.assert_not_called()

    def test_firebase_deploy_skipped_when_no_firebase_files_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            orchestrator, manager, _ = self._firebase_orchestrator(repository, runner)
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch(
                    "tui.orchestrator.load_firebase_status",
                    return_value=FirebaseStatus(True, "demo-app"),
                ),
                patch("tui.orchestrator.firebase_changes_pending", return_value=False) as pending,
                patch("tui.orchestrator.deploy_firebase") as deploy,
            ):
                result = orchestrator.run("Build it", "codex", "gpt-6-astra", "medium")

        self.assertTrue(result.succeeded)
        pending.assert_called()
        deploy.assert_not_called()

    def test_firebase_deploy_runs_once_after_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            events = []
            orchestrator, manager, context = self._firebase_orchestrator(
                repository, runner, events
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch(
                    "tui.orchestrator.load_firebase_status",
                    return_value=FirebaseStatus(True, "demo-app"),
                ),
                patch("tui.orchestrator.firebase_changes_pending", return_value=True),
                patch(
                    "tui.orchestrator.deploy_firebase",
                    return_value=DeployResult(True, "Deploy complete!"),
                ) as deploy,
            ):
                result = orchestrator.run("Build it", "codex", "gpt-6-astra", "medium")

        self.assertTrue(result.succeeded)
        deploy.assert_called_once()
        self.assertEqual(deploy.call_args.args[0], context.path)
        self.assertEqual(deploy.call_args.kwargs["project_id"], "demo-app")
        self.assertTrue(any(phase == "firebase" for phase, _, _ in events))
        self.assertTrue(any(phase == "ready" for phase, _, _ in events))

    def test_firebase_deploy_failure_repairs_then_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            orchestrator, manager, context = self._firebase_orchestrator(repository, runner)
            (context.path / ".agents" / "profiles").mkdir(parents=True)
            (context.path / ".agents" / "profiles" / "coding.md").write_text(
                "CODING_PROFILE_FOR_FIREBASE_REPAIR", encoding="utf-8"
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch(
                    "tui.orchestrator.load_firebase_status",
                    return_value=FirebaseStatus(True, "demo-app"),
                ),
                patch("tui.orchestrator.firebase_changes_pending", return_value=True),
                patch(
                    "tui.orchestrator.deploy_firebase",
                    side_effect=[
                        DeployResult(False, "firestore.rules line 4: unexpected token"),
                        DeployResult(True, "Deploy complete!"),
                    ],
                ) as deploy,
            ):
                result = orchestrator.run("Build it", "codex", "gpt-6-astra", "medium")

        self.assertTrue(result.succeeded)
        self.assertEqual(deploy.call_count, 2)
        repair_prompt = runner.run.call_args.args[0].prompt
        self.assertIn("Repair the failing Firebase deploy", repair_prompt)
        self.assertIn("firestore.rules line 4", repair_prompt)
        self.assertIn("CODING_PROFILE_FOR_FIREBASE_REPAIR", repair_prompt)
        manager.commit_changes.assert_any_call(
            context.path,
            "Daedalus: Build it (Firebase repair 1)",
        )

    def test_exhausted_firebase_deploy_fails_with_each_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", 0, "done")
            orchestrator, manager, _ = self._firebase_orchestrator(
                repository, runner, task_verification_attempt_limit=2
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch(
                    "tui.orchestrator.load_firebase_status",
                    return_value=FirebaseStatus(True, "demo-app"),
                ),
                patch("tui.orchestrator.firebase_changes_pending", return_value=True),
                patch(
                    "tui.orchestrator.deploy_firebase",
                    return_value=DeployResult(False, "permission denied"),
                ),
            ):
                result = orchestrator.run("Build it", "codex", "gpt-6-astra", "medium")

        self.assertFalse(result.succeeded)
        self.assertIn("Firebase deploy failed after 2 attempts", result.error)
        self.assertIn("permission denied", result.error)

    def test_integration_resume_does_not_push_migrations(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(verification_commands=(("true",),)),
                lambda *_: None,
            )
            with (
                patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
                patch("tui.orchestrator.run_verification", return_value=VerificationResult(True, "")),
                patch("tui.orchestrator.migrations_pending") as pending,
                patch("tui.orchestrator.push_migrations") as push,
            ):
                result = orchestrator.run(
                    "Build it",
                    "codex",
                    "gpt-5.6-luna",
                    "medium",
                    existing_context=context,
                    resume_from="integration",
                )

        self.assertTrue(result.succeeded)
        pending.assert_not_called()
        push.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class InterruptionTests(unittest.TestCase):
    def test_interrupted_agent_preserves_worktree_and_reports_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            runner.run.return_value = AgentResult("codex", -15, "", stopped_reason="interrupted")
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            events = []
            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda phase, message, channel: events.append((phase, message, channel)),
            )
            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager):
                from tui.agent_runner import AgentControl

                control = AgentControl()
                control.request_interrupt()
                result = orchestrator.run("Build it", "codex", "gpt-5.6-luna", "medium", control=control)

        self.assertFalse(result.succeeded)
        self.assertTrue(result.interrupted)
        self.assertFalse(result.cancelled)
        self.assertIs(result.context, context)
        manager.remove_cancelled.assert_not_called()
        manager.remove_successful.assert_not_called()
        self.assertTrue(any(phase == "interrupted" for phase, _, _ in events))
        self.assertFalse(any(channel == "error" for _, _, channel in events))

    def test_interruption_is_checked_before_promotion_and_gate_receives_a_stop_check(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            runner = Mock()
            context = WorktreeContext(repository, "task", "base", "agent/task-task", repository / "worktree")
            manager = Mock()
            manager.create.return_value = context
            manager.head.return_value = "new-commit"
            manager.capture_primary.return_value = "base"
            gate_calls = []

            def gate(sequence, operation, stop_check=None):
                gate_calls.append(stop_check)
                operation()

            from tui.agent_runner import AgentControl

            control = AgentControl()

            def integrate(*_args, **_kwargs):
                # The user presses Ctrl+C after integration but before promotion.
                control.request_interrupt()

            orchestrator = LocalOrchestrator(
                repository,
                runner,
                OrchestrationSettings(),
                lambda _phase, _message, _channel: None,
                integration_gate=gate,
            )
            with patch("tui.orchestrator.GitWorktreeManager", return_value=manager), patch.object(
                orchestrator, "run_agent", return_value=AgentResult("codex", 0, "done")
            ), patch.object(orchestrator, "verify_with_repairs"), patch.object(
                orchestrator, "push_migrations_with_repairs"
            ), patch.object(orchestrator, "deploy_firebase_with_repairs"), patch.object(
                orchestrator, "integrate", side_effect=integrate
            ):
                result = orchestrator.run("Build it", "codex", "luna", "medium", control=control)

        self.assertTrue(result.interrupted)
        manager.promote.assert_not_called()
        manager.remove_successful.assert_not_called()
        self.assertEqual(len(gate_calls), 1)
        self.assertIsNotNone(gate_calls[0])
        self.assertEqual(gate_calls[0](), "interrupted")

    def test_two_argument_gates_remain_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            calls = []
            orchestrator = LocalOrchestrator(
                repository,
                Mock(),
                OrchestrationSettings(),
                lambda *_: None,
                integration_gate=lambda sequence, operation: calls.append(sequence) or operation(),
            )
            ran = []
            orchestrator._run_integration_gate(7, lambda: ran.append(True), None)
        self.assertEqual((calls, ran), ([7], [True]))
