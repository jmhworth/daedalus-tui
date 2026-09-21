import json
import signal
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tui.agent_runner import (
    AgentControl,
    AgentLogEvent,
    AgentRequest,
    AgentRunner,
    ProviderAuthPolicy,
)
from tui.environment import agent_environment, read_env_file


class FakeStream:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def readline(self):
        try:
            return next(self.chunks)
        except StopIteration:
            return ""

    def close(self):
        return None


class FakeProcess:
    def __init__(self, stdout=None, stderr=None, returncode=0):
        self.stdout = FakeStream(stdout or [])
        self.stderr = FakeStream(stderr or [])
        self.returncode = returncode

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


class InterruptibleProcess(FakeProcess):
    def __init__(self):
        super().__init__([], [], returncode=None)
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15


class AgentRunnerTests(unittest.TestCase):
    def request(self, provider="codex", model="gpt-5.6-luna", reasoning="medium"):
        return AgentRequest(
            "Inspect this project",
            Path("/workspace/project"),
            provider,
            model,
            reasoning,
            (Path("/workspace/project"),),
        )

    def test_builds_codex_command_and_maps_reasoning(self):
        self.assertEqual(
            AgentRunner().command_for(self.request(reasoning="extra-high")),
            [
                "codex", "exec", "-m", "gpt-5.6-luna", "-c",
                'model_reasoning_effort="xhigh"', "--sandbox", "workspace-write",
                "--add-dir", "/workspace/project", "--json", "Inspect this project",
            ],
        )

    def test_builds_exact_cursor_command(self):
        self.assertEqual(
            AgentRunner().command_for(self.request("cursor", "cursor", "")),
            ["agent", "-p", "--output-format", "stream-json", "--force", "Inspect this project"],
        )

    def test_claude_command_uses_project_settings(self):
        request = self.request("claude", "claude-opus-5", "high")
        request = AgentRequest(
            request.prompt, request.directory, request.provider, request.model,
            request.reasoning, settings_file=Path("/repo/permissions.json"),
            allowed_tools=("Bash(python3:*)",),
        )
        command = AgentRunner().command_for(request)
        self.assertEqual(command[command.index("--settings") + 1], "/repo/permissions.json")
        self.assertIn("Bash(python3:*)", command)

    def test_claude_receives_project_environment_without_worktree_secret_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            primary = Path(directory) / "primary"
            worktree = Path(directory) / "worktree"
            primary.mkdir()
            worktree.mkdir()
            secret_file = primary / "fstore.env"
            secret_file.write_text("R2_BUCKET=research\nANTHROPIC_API_KEY=wrong-auth\n", encoding="utf-8")
            with patch.dict("tui.environment.os.environ", {"PATH": "/usr/bin"}, clear=True):
                environment = agent_environment(
                    "claude", worktree, (secret_file,), ("ANTHROPIC_API_KEY",)
                )
            self.assertEqual(environment["R2_BUCKET"], "research")
            self.assertNotIn("ANTHROPIC_API_KEY", environment)
            self.assertFalse((worktree / "fstore.env").exists())

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/codex")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_emits_only_completed_agent_messages_and_suppresses_stderr(self, popen, _which):
        events = [
            {"type": "thread.started"},
            {"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}},
            {"type": "item.completed", "item": {"type": "file_change", "path": "feature.md"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Implemented the second page at app/legal/page.tsx"}},
            {"type": "turn.completed", "usage": {"input_tokens": 120, "output_tokens": 45}},
        ]
        popen.return_value = FakeProcess([*(json.dumps(event) + "\n" for event in events)], ["normal diagnostic\n"])
        output = []
        result = AgentRunner().run(self.request(), output.append)

        self.assertTrue(result.succeeded)
        self.assertEqual([event.text for event in output], ["Implemented the second page at app/legal/page.tsx"])
        self.assertTrue(all(isinstance(event, AgentLogEvent) for event in output))
        self.assertEqual(result.output, "Implemented the second page at app/legal/page.tsx")
        self.assertEqual(result.stderr, "normal diagnostic\n")
        self.assertEqual(result.tokens_consumed, 165)
        self.assertEqual(popen.call_args.kwargs["cwd"], Path("/workspace/project"))
        self.assertIs(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    @patch("tui.agent_runner._TimeoutTracker.reset")
    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/codex")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_refreshes_timeout_for_every_stdout_update(self, popen, _which, reset):
        events = [
            {"type": "thread.started"},
            {"type": "item.completed", "item": {"type": "file_change", "path": "feature.md"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Updated the feature."}},
        ]
        popen.return_value = FakeProcess([*(json.dumps(event) + "\n" for event in events)])
        request = self.request()
        request = AgentRequest(
            request.prompt,
            request.directory,
            request.provider,
            request.model,
            request.reasoning,
            request.writable_directories,
            request.environment_files,
            request.control,
            450,
        )

        result = AgentRunner().run(request, lambda _event: None)

        self.assertTrue(result.succeeded)
        self.assertEqual(reset.call_count, len(events))

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/codex")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_output_callback_failure_does_not_strand_agent_reader(self, popen, _which):
        event = {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}}
        popen.return_value = FakeProcess([json.dumps(event) + "\n"], [])

        result = AgentRunner().run(self.request(), Mock(side_effect=RuntimeError("UI closed")))

        self.assertTrue(result.succeeded)
        self.assertEqual(result.output, "done")

    @patch("tui.agent_runner.os.killpg")
    @patch("tui.agent_runner.os.getpgid", return_value=123)
    def test_termination_kills_the_complete_agent_process_group(self, _getpgid, killpg):
        process = Mock(pid=123)
        process.wait.side_effect = [subprocess.TimeoutExpired(["agent"], 2), 0]

        AgentRunner._terminate_process(process)

        self.assertEqual(
            killpg.call_args_list,
            [
                unittest.mock.call(123, signal.SIGTERM),
                unittest.mock.call(123, signal.SIGKILL),
            ],
        )

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/codex")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_failed_process_surfaces_stderr_only_in_error(self, popen, _which):
        popen.return_value = FakeProcess([], ["permission denied\n"], returncode=2)
        output = []
        result = AgentRunner().run(self.request(), output.append)

        self.assertFalse(result.succeeded)
        self.assertEqual(output, [])
        self.assertIn("exit code 2", result.error)
        self.assertIn("permission denied", result.error)

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/agent")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_cursor_failure_without_stderr_has_actionable_diagnostics(self, popen, _which):
        popen.return_value = FakeProcess([], [], returncode=1)
        result = AgentRunner().run(self.request("cursor", "cursor", ""), lambda *_: None)

        self.assertFalse(result.succeeded)
        self.assertIn("No diagnostics were emitted", result.error)
        self.assertIn("CURSOR_API_KEY", result.error)
        self.assertIn("agent login", result.error)

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/agent")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_parses_cursor_json_result_without_streaming_raw_output(self, popen, _which):
        events = [
            {"type": "assistant", "message": {"role": "assistant", "content": []}},
            {"type": "result", "result": "Implemented the page.", "usage": {"total_tokens": 321}},
        ]
        popen.return_value = FakeProcess([*(json.dumps(event) + "\n" for event in events)], ["diagnostic\n"])
        output = []
        result = AgentRunner().run(self.request("cursor", "cursor", ""), output.append)

        self.assertTrue(result.succeeded)
        self.assertEqual(result.output, "Implemented the page.")
        self.assertEqual(result.tokens_consumed, 321)
        self.assertEqual(output, [])
        self.assertIn("env", popen.call_args.kwargs)

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/agent")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_streams_cursor_assistant_deltas(self, popen, _which):
        events = [
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "I'll "}]},
            },
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "inspect the files."}]},
            },
            {"type": "result", "result": "I'll inspect the files."},
        ]
        popen.return_value = FakeProcess([*(json.dumps(event) + "\n" for event in events)])
        output = []

        result = AgentRunner().run(self.request("cursor", "cursor", ""), output.append)

        self.assertTrue(result.succeeded)
        self.assertEqual([event.text for event in output], ["I'll ", "inspect the files."])
        self.assertTrue(result.output_streamed)

    @patch("tui.agent_runner.agent_environment", return_value={"CURSOR_API_KEY": "from-env-file"})
    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/agent")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_passes_cursor_api_key_to_subprocess(self, popen, _which, _environment):
        popen.return_value = FakeProcess([json.dumps({"result": "done"})], [])
        AgentRunner(auth_policy=ProviderAuthPolicy(account_login=False)).run(
            self.request("cursor", "cursor", ""), lambda *_: None
        )

        self.assertEqual(popen.call_args.kwargs["env"]["CURSOR_API_KEY"], "from-env-file")

    def test_builds_claude_command_with_model_effort_and_permission_mode(self):
        self.assertEqual(
            AgentRunner().command_for(self.request("claude", "claude-opus-5", "extra-high")),
            [
                "claude", "--print", "--output-format", "stream-json", "--verbose",
                "--model", "claude-opus-5", "--effort", "xhigh",
                "--permission-mode", "acceptEdits", "Inspect this project",
            ],
        )

    def test_claude_command_allowlists_configured_and_per_run_tools(self):
        """`claude --print` cannot prompt, so verification commands must be pre-approved."""
        runner = AgentRunner(claude_allowed_tools=("Bash(git status:*)", "Bash(npm test:*)"))
        request = AgentRequest(
            "Inspect this project",
            Path("/workspace/project"),
            "claude",
            "claude-opus-5",
            "high",
            (Path("/workspace/project"),),
            allowed_tools=("Bash(npm test:*)", "Bash(python3 -m pytest:*)"),
        )
        command = runner.command_for(request)

        start = command.index("--allowedTools")
        self.assertEqual(
            command[start + 1 : start + 4],
            ["Bash(git status:*)", "Bash(npm test:*)", "Bash(python3 -m pytest:*)"],
        )
        # --allowedTools is variadic: a single-argument option must follow it
        # so the trailing prompt is never absorbed into the list.
        self.assertEqual(command[start + 4], "--model")
        self.assertEqual(command[-1], "Inspect this project")

    def test_claude_command_omits_allowlist_when_nothing_is_allowed(self):
        command = AgentRunner().command_for(self.request("claude", "claude-opus-5", "high"))
        self.assertNotIn("--allowedTools", command)

    def test_claude_command_keeps_the_prompt_after_a_single_argument_option(self):
        """--add-dir is variadic, so the prompt must never follow it directly."""
        request = AgentRequest(
            "Inspect this project",
            Path("/workspace/project"),
            "claude",
            "claude-sonnet-5",
            "high",
            (Path("/workspace/project"), Path("/workspace/shared")),
        )
        command = AgentRunner().command_for(request)

        self.assertEqual(command[-1], "Inspect this project")
        self.assertEqual(command[command.index("--add-dir") + 1], "/workspace/shared")
        self.assertTrue(command[command.index("--add-dir") + 2].startswith("--"))
        # The worktree is already the working directory and is not re-added.
        self.assertEqual(command.count("--add-dir"), 1)

    def test_claude_permission_mode_is_configurable(self):
        runner = AgentRunner(claude_permission_mode="bypassPermissions")
        command = runner.command_for(self.request("claude", "claude-opus-5", "high"))
        self.assertEqual(command[command.index("--permission-mode") + 1], "bypassPermissions")

    def test_claude_reasoning_supports_max_effort(self):
        command = AgentRunner().command_for(self.request("claude", "claude-opus-5", "max"))
        self.assertEqual(command[command.index("--effort") + 1], "max")

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/claude")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_streams_claude_assistant_blocks_as_separate_messages(self, popen, _which):
        events = [
            {"type": "system", "subtype": "init", "session_id": "abc"},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Reading the feature file."}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "name": "Edit", "input": {}}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Updated tui/config.py."}],
                },
            },
            {
                "type": "result",
                "subtype": "success",
                "result": "Updated tui/config.py.",
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 30,
                    "cache_read_input_tokens": 900,
                    "cache_creation_input_tokens": 58,
                },
            },
        ]
        popen.return_value = FakeProcess([*(json.dumps(event) + "\n" for event in events)])
        output = []

        result = AgentRunner().run(self.request("claude", "claude-opus-5", "high"), output.append)

        self.assertTrue(result.succeeded)
        self.assertEqual(
            [event.text for event in output],
            ["Reading the feature file.", "Updated tui/config.py."],
        )
        # Whole blocks, not deltas: the transcript keeps them separate.
        self.assertEqual(result.output, "Reading the feature file.\n\nUpdated tui/config.py.")
        self.assertTrue(result.output_streamed)
        self.assertEqual(result.tokens_consumed, 1000)

    @patch("tui.agent_runner.shutil.which", return_value=None)
    def test_reports_missing_claude_cli(self, _which):
        result = AgentRunner().run(self.request("claude", "claude-opus-5", "high"), lambda *_: None)
        self.assertFalse(result.succeeded)
        self.assertIn("Claude Code CLI is unavailable", result.error)
        self.assertIn("`claude` is on PATH", result.error)

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/claude")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_account_login_removes_provider_api_keys_from_the_subprocess(self, popen, _which):
        popen.return_value = FakeProcess([], [])
        policy = ProviderAuthPolicy(
            account_login=True,
            api_key_variables={"claude": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")},
        )
        with patch.dict(
            "os.environ",
            {"ANTHROPIC_API_KEY": "sk-test", "ANTHROPIC_AUTH_TOKEN": "tok", "PATH": "/usr/bin"},
            clear=True,
        ):
            AgentRunner(auth_policy=policy).run(
                self.request("claude", "claude-opus-5", "high"), lambda *_: None
            )

        environment = popen.call_args.kwargs["env"]
        self.assertNotIn("ANTHROPIC_API_KEY", environment)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", environment)
        self.assertEqual(environment["PATH"], "/usr/bin")

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/claude")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_api_key_mode_leaves_the_environment_inherited(self, popen, _which):
        popen.return_value = FakeProcess([], [])
        policy = ProviderAuthPolicy(
            account_login=False,
            api_key_variables={"claude": ("ANTHROPIC_API_KEY",)},
        )
        AgentRunner(auth_policy=policy).run(
            self.request("claude", "claude-opus-5", "high"), lambda *_: None
        )

        self.assertNotIn("env", popen.call_args.kwargs)

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/claude")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_claude_failure_suggests_signing_in_when_account_login_is_active(self, popen, _which):
        popen.return_value = FakeProcess([], ["Invalid API key\n"], returncode=1)
        policy = ProviderAuthPolicy(
            account_login=True, api_key_variables={"claude": ("ANTHROPIC_API_KEY",)}
        )

        result = AgentRunner(auth_policy=policy).run(
            self.request("claude", "claude-opus-5", "high"), lambda *_: None
        )

        self.assertFalse(result.succeeded)
        self.assertIn("Claude Code CLI failed with exit code 1", result.error)
        self.assertIn("claude auth login", result.error)

    @patch("tui.agent_runner.shutil.which", return_value=None)
    def test_reports_missing_cli(self, _which):
        result = AgentRunner().run(self.request(), lambda *_: None)
        self.assertFalse(result.succeeded)
        self.assertIn("Codex CLI is unavailable", result.error)

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/codex")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_pause_terminates_active_process_without_emitting_an_error(self, popen, _which):
        process = InterruptibleProcess()
        popen.return_value = process
        control = AgentControl()
        control.request_pause()
        request = self.request()
        request = AgentRequest(
            request.prompt,
            request.directory,
            request.provider,
            request.model,
            request.reasoning,
            request.writable_directories,
            request.environment_files,
            control,
        )

        result = AgentRunner().run(request, lambda _event: None)

        self.assertEqual(result.stopped_reason, "paused")
        self.assertTrue(process.terminated)
        self.assertIsNone(result.error)

    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/codex")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_timeout_returns_retryable_connectivity_error(self, popen, _which):
        process = InterruptibleProcess()
        popen.return_value = process
        request = self.request()
        request = AgentRequest(
            request.prompt,
            request.directory,
            request.provider,
            request.model,
            request.reasoning,
            request.writable_directories,
            request.environment_files,
            None,
            0.01,
        )

        result = AgentRunner().run(request, lambda _event: None)

        self.assertFalse(result.succeeded)
        self.assertTrue(result.timed_out)
        self.assertIn("timed out", result.error)
        self.assertIn("internet connection", result.error)
        self.assertTrue(process.terminated)

    def test_reads_cursor_env_file_without_requiring_python_dotenv(self):
        with unittest.mock.patch("tui.environment.Path.is_file", return_value=True), unittest.mock.patch(
            "tui.environment.Path.read_text", return_value="export CURSOR_API_KEY='secret-value'\n"
        ):
            self.assertEqual(read_env_file(Path("/tmp/.env")), {"CURSOR_API_KEY": "secret-value"})


if __name__ == "__main__":
    unittest.main()


class InterruptSignalTests(unittest.TestCase):
    @patch("tui.agent_runner.shutil.which", return_value="/usr/local/bin/codex")
    @patch("tui.agent_runner.subprocess.Popen")
    def test_interrupt_terminates_the_process_and_reports_the_reason(self, popen, _which):
        process = InterruptibleProcess()
        popen.return_value = process
        control = AgentControl()
        control.request_interrupt()
        request = AgentRequest(
            "Inspect this project",
            Path("/workspace/project"),
            "codex",
            "gpt-5.6-luna",
            "medium",
            (Path("/workspace/project"),),
            control=control,
        )

        result = AgentRunner().run(request, lambda _event: None)

        self.assertEqual(result.stopped_reason, "interrupted")
        self.assertTrue(process.terminated)
        self.assertIsNone(result.error)

    def test_stop_reason_precedence_and_clearing(self):
        control = AgentControl()
        self.assertIsNone(control.stop_reason)
        control.request_pause()
        control.request_interrupt()
        self.assertEqual(control.stop_reason, "interrupted")
        control.request_cancel()
        self.assertEqual(control.stop_reason, "cancelled")
        control.clear_interrupt()
        control.clear_pause()
        self.assertEqual(control.stop_reason, "cancelled")
