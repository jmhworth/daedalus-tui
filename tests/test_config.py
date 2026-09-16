from dataclasses import replace
import re
import tempfile
import unittest
from pathlib import Path

from tui.config import LayoutSettings, load_coding_statistics_settings, load_orchestration_settings, load_tui_settings
from tui.git_worktree import DIRTY_PRIMARY_COMMIT_MESSAGE


class ConfigTests(unittest.TestCase):
    def test_loads_all_provider_and_orchestration_settings(self):
        root = Path(__file__).resolve().parents[1]
        settings = load_tui_settings(root / "parameter_files" / "daedalus-tui.toml")
        orchestration = load_orchestration_settings(root / "parameter_files" / "daedalus-tui-orchestration.toml")

        self.assertEqual(settings.default_provider, "claude")
        self.assertEqual(settings.default_model, "claude-opus-5")
        self.assertEqual(settings.default_reasoning, "high")
        self.assertEqual([item.value for item in settings.codex_models], [
            "gpt-6-astra", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
        ])
        self.assertEqual([item.value for item in settings.codex_reasoning], [
            "light", "medium", "high", "extra-high",
        ])
        self.assertEqual([item.value for item in settings.modes], ["coding", "ask", "plan"])
        self.assertEqual(settings.output_width, "95%")
        self.assertEqual(settings.task_inbox_widths, (1, 9, 14, 7))
        self.assertEqual(settings.layout, LayoutSettings(100, 32, 8, 4))
        self.assertEqual(orchestration.primary_branch, "main")
        self.assertEqual(orchestration.resolver_attempt_limit, 3)
        self.assertEqual(orchestration.max_concurrent_tasks, 4)
        self.assertEqual(orchestration.agent_timeout_seconds, 450)
        self.assertTrue(orchestration.graphify_update_enabled)
        self.assertEqual(orchestration.graphify_executable, "graphify")
        self.assertTrue(orchestration.supabase_db_push_enabled)
        self.assertEqual(orchestration.supabase_executable, "supabase")
        self.assertTrue(orchestration.firebase_deploy_enabled)
        self.assertEqual(orchestration.firebase_executable, "firebase")

    def test_loads_claude_provider_models_effort_and_permission_mode(self):
        root = Path(__file__).resolve().parents[1]
        settings = load_tui_settings(root / "parameter_files" / "daedalus-tui.toml")

        self.assertIn("claude", [item.value for item in settings.providers])
        self.assertEqual(
            [item.value for item in settings.claude_models],
            ["claude-opus-5", "claude-sonnet-5", "claude-fable-5-1", "claude-haiku-4-5-20251001"],
        )
        # Claude Code exposes an effort level Codex has no equivalent for.
        self.assertIn("max", [item.value for item in settings.claude_reasoning])
        self.assertEqual(settings.claude.permission_mode, "acceptEdits")
        # Non-interactive Claude runs need the project checks pre-approved.
        self.assertIn("Bash(npm test:*)", settings.claude.allowed_tools)
        self.assertIn("Bash(python3 -m pytest:*)", settings.claude.allowed_tools)

    def test_claude_allowed_tools_must_be_a_string_array(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "parameter_files" / "daedalus-tui.toml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daedalus-tui.toml"
            path.write_text(
                re.sub(r"allowed_tools = \[.*?\]", 'allowed_tools = "Bash(*)"', source, count=1, flags=re.S),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as raised:
                load_tui_settings(path)
        self.assertIn("claude.allowed_tools", str(raised.exception))

    def test_provider_cascade_falls_back_to_a_legal_model_and_effort(self):
        root = Path(__file__).resolve().parents[1]
        settings = load_tui_settings(root / "parameter_files" / "daedalus-tui.toml")

        # The Claude default is not a Codex model, so the first Codex one wins.
        self.assertEqual(settings.default_model_for("codex"), "gpt-6-astra")
        self.assertEqual(settings.default_model_for("claude"), "claude-opus-5")
        self.assertEqual(settings.default_model_for("cursor"), "cursor")
        self.assertEqual(settings.default_reasoning_for("claude"), "high")
        self.assertEqual(settings.default_reasoning_for("cursor"), "")
        self.assertEqual(settings.reasoning_for("cursor"), ())

    def test_account_auth_mode_lists_provider_key_variables_to_strip(self):
        root = Path(__file__).resolve().parents[1]
        settings = load_tui_settings(root / "parameter_files" / "daedalus-tui.toml")

        self.assertTrue(settings.auth.uses_account_login)
        self.assertEqual(
            settings.auth.for_provider("claude").api_key_variables,
            ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        )
        self.assertEqual(
            settings.auth.for_provider("claude").sign_in_command,
            ("claude", "auth", "login"),
        )
        policy = settings.auth.runner_policy()
        self.assertTrue(policy.account_login)
        self.assertEqual(policy.stripped_variables("cursor"), ("CURSOR_API_KEY",))
        self.assertEqual(policy.stripped_variables("codex"), ("OPENAI_API_KEY",))

    def test_api_key_mode_strips_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.toml"
            path.write_text(
                """
                providers = [{ label = "Codex", value = "codex" }]
                codex_models = [{ label = "Model", value = "model" }]
                codex_reasoning = [{ label = "High", value = "high" }]

                [auth]
                mode = "api-key"

                [auth.codex]
                label = "Codex"
                api_key_variables = ["OPENAI_API_KEY"]
                """,
                encoding="utf-8",
            )
            policy = load_tui_settings(path).auth.runner_policy()

            self.assertFalse(policy.account_login)
            self.assertEqual(policy.stripped_variables("codex"), ())

    def test_rejects_an_unknown_auth_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.toml"
            path.write_text(
                """
                providers = [{ label = "Codex", value = "codex" }]
                codex_models = [{ label = "Model", value = "model" }]
                codex_reasoning = [{ label = "High", value = "high" }]

                [auth]
                mode = "oauth"
                """,
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "auth.mode"):
                load_tui_settings(path)

    def test_rejects_a_claude_provider_without_models(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "claude.toml"
            path.write_text(
                """
                providers = [
                  { label = "Codex", value = "codex" },
                  { label = "Claude Code", value = "claude" },
                ]
                codex_models = [{ label = "Model", value = "model" }]
                codex_reasoning = [{ label = "High", value = "high" }]
                """,
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "claude_models"):
                load_tui_settings(path)

    def test_loads_project_discovery_breadth(self):
        root = Path(__file__).resolve().parents[1]
        settings = load_tui_settings(root / "parameter_files" / "daedalus-tui.toml")

        self.assertTrue(settings.project_discovery.include_git_repositories)
        self.assertFalse(settings.project_discovery.include_all_directories)
        self.assertIn("node_modules", settings.project_discovery.skipped_directory_names)

    def test_loads_target_branch_and_primary_branch_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            target_path = Path(directory) / "target.toml"
            target_path.write_text('target_branch = "develop"\nverification_commands = []\n', encoding="utf-8")
            alias_path = Path(directory) / "alias.toml"
            alias_path.write_text('primary_branch = "release"\nverification_commands = []\n', encoding="utf-8")

            self.assertEqual(load_orchestration_settings(target_path).primary_branch, "develop")
            self.assertEqual(load_orchestration_settings(alias_path).primary_branch, "release")

    def test_dirty_primary_autocommit_defaults_to_committing_and_pushing(self):
        root = Path(__file__).resolve().parents[1]
        orchestration = load_orchestration_settings(
            root / "parameter_files" / "daedalus-tui-orchestration.toml"
        )

        self.assertTrue(orchestration.dirty_primary_autocommit_enabled)
        self.assertTrue(orchestration.dirty_primary_push_enabled)
        self.assertEqual(orchestration.git_remote, "origin")
        self.assertTrue(orchestration.dirty_primary_commit_message)

    def test_dirty_primary_autocommit_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orchestration.toml"
            path.write_text(
                "dirty_primary_autocommit_enabled = false\n"
                "dirty_primary_push_enabled = false\n"
                'git_remote = "upstream"\n'
                'dirty_primary_commit_message = "   "\n'
                "verification_commands = []\n",
                encoding="utf-8",
            )
            settings = load_orchestration_settings(path)

            self.assertFalse(settings.dirty_primary_autocommit_enabled)
            self.assertFalse(settings.dirty_primary_push_enabled)
            self.assertEqual(settings.git_remote, "upstream")
            # A blank message would make `git commit -m` fail; fall back instead.
            self.assertEqual(settings.dirty_primary_commit_message, DIRTY_PRIMARY_COMMIT_MESSAGE)

    def test_loads_coding_statistics_forecast_settings(self):
        root = Path(__file__).resolve().parents[1]
        statistics = load_coding_statistics_settings(
            root / "parameter_files" / "daedalus-tui-coding-statistics.toml"
        )

        self.assertEqual(statistics.recent_window_hours, 1)
        self.assertEqual(statistics.forecast_days, 7)
        self.assertEqual(statistics.thirty_day_forecast_days, 30)

    def test_rejects_non_positive_layout_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.toml"
            path.write_text(
                """
                providers = [{ label = "Codex", value = "codex" }]
                codex_models = [{ label = "Model", value = "model" }]
                codex_reasoning = [{ label = "High", value = "high" }]
                [layout]
                compact_width = 0
                """,
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "layout values must be positive"):
                load_tui_settings(path)

    def test_loads_custom_layout_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.toml"
            path.write_text(
                """
                providers = [{ label = "Codex", value = "codex" }]
                codex_models = [{ label = "Model", value = "model" }]
                codex_reasoning = [{ label = "High", value = "high" }]
                [layout]
                compact_width = 88
                wide_control_min_width = 14
                short_height = 24
                compact_task_sidebar_height = 6
                compact_prompt_height = 3
                """,
                encoding="utf-8",
            )

            self.assertEqual(
                load_tui_settings(path).layout,
                LayoutSettings(88, 24, 6, 3, 14),
            )


if __name__ == "__main__":
    unittest.main()


class PromptingAndUsageSettingsTests(unittest.TestCase):
    def test_loads_prompting_settings_anchored_to_the_tui_project(self):
        from tui.config import load_prompting_settings

        root = Path(__file__).resolve().parents[1]
        settings = load_prompting_settings(root / "parameter_files" / "daedalus-tui-prompting.toml")
        self.assertEqual(settings.data_root, root)
        self.assertEqual(settings.draft_autosave_delay_ms, 300)
        self.assertEqual(settings.task_title_length, 60)
        self.assertFalse(settings.viewer_visible_by_default)
        self.assertEqual((settings.viewer_minimum_width, settings.main_minimum_width), (40, 80))
        self.assertTrue(settings.viewer_hard_line_breaks)
        self.assertTrue(settings.viewer_action_items_by_default)
        self.assertEqual(settings.viewer_action_item_limit, 6)
        self.assertEqual(settings.error_log_max_bytes, 2_000_000)
        self.assertEqual(settings.error_log_backup_count, 3)

    def test_relative_data_root_resolves_against_the_parameter_files_owner_not_cwd(self):
        from tui.config import load_prompting_settings

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "installed-tui"
            (project / "parameter_files").mkdir(parents=True)
            parameter_path = project / "parameter_files" / "daedalus-tui-prompting.toml"
            parameter_path.write_text('[storage]\ndata_root = "state"\n', encoding="utf-8")
            settings = load_prompting_settings(parameter_path)
            self.assertEqual(settings.data_root, (project / "state").resolve())
            parameter_path.write_text(f'[storage]\ndata_root = "{Path(directory) / "abs"}"\n', encoding="utf-8")
            self.assertEqual(load_prompting_settings(parameter_path).data_root, (Path(directory) / "abs").resolve())

    def test_generated_storage_folders_are_never_discovered_as_projects(self):
        from tui.projects import discover_projects

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "prompts" / "feature_files").mkdir(parents=True)
            (root / "errors").mkdir()
            (root / "real" / "feature_files").mkdir(parents=True)
            settings = load_tui_settings(Path(__file__).resolve().parents[1] / "parameter_files" / "daedalus-tui.toml")
            discovered = discover_projects(root, replace(settings.project_discovery, include_all_directories=True))
            self.assertEqual([project.name for project in discovered], ["real"])
            self.assertIn("prompts", settings.project_discovery.skipped_directory_names)

    def test_loads_usage_bar_settings(self):
        root = Path(__file__).resolve().parents[1]
        settings = load_tui_settings(root / "parameter_files" / "daedalus-tui.toml")
        self.assertTrue(settings.usage.enabled)
        self.assertEqual(settings.usage.interval_seconds, 60)
        self.assertEqual(set(settings.usage.providers), {"claude", "codex"})
        self.assertEqual(settings.usage.providers["codex"].command, ())
        self.assertEqual(settings.usage.providers["claude"].label, "Claude")
        # Scalar tuning keys must not be mistaken for provider tables.
        self.assertEqual(settings.usage.session_scan_limit, 12)
        self.assertEqual(settings.usage.session_tail_bytes, 262_144)
        self.assertEqual(settings.usage.bar_width, 12)
        self.assertEqual(settings.usage.claude_projects_dir, "~/.claude/projects")
        self.assertEqual(settings.usage.claude_transcript_days, 30)
        # The statistics screen's account-wide total looks back much further
        # than the bar's recent window.
        self.assertEqual(settings.usage.claude_account_scan_days, 3650)
        # 0 means the Claude bars calibrate against the busiest recorded window.
        self.assertEqual(settings.usage.claude_five_hour_token_limit, 0)
        self.assertEqual(settings.usage.claude_weekly_token_limit, 0)
