import tempfile
import unittest
from pathlib import Path

from tui.config import (
    LayoutSettings,
    load_coding_statistics_settings,
    load_command_menu_settings,
    load_orchestration_settings,
    load_tui_settings,
)


class ConfigTests(unittest.TestCase):
    def test_loads_all_provider_and_orchestration_settings(self):
        root = Path(__file__).resolve().parents[1]
        settings = load_tui_settings(root / "parameter_files" / "daedalus-tui.toml")
        orchestration = load_orchestration_settings(root / "parameter_files" / "daedalus-tui-orchestration.toml")

        self.assertEqual(settings.default_model, "gpt-5.6-luna")
        self.assertEqual(settings.default_reasoning, "high")
        self.assertEqual([item.value for item in settings.codex_models], [
            "gpt-6-astra", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
        ])
        self.assertEqual([item.value for item in settings.codex_reasoning], [
            "light", "medium", "high", "extra-high", "max",
        ])
        self.assertEqual([item.value for item in settings.modes], ["coding", "ask", "plan"])
        self.assertEqual(settings.output_width, "95%")
        self.assertEqual(settings.task_inbox_widths, (1, 9, 14, 7))
        self.assertEqual(settings.layout, LayoutSettings(100, 32, 8, 8))
        self.assertEqual(orchestration.primary_branch, "main")
        self.assertEqual(orchestration.resolver_attempt_limit, 3)
        self.assertEqual(orchestration.max_concurrent_tasks, 4)
        self.assertEqual(orchestration.agent_timeout_seconds, 450)
        self.assertTrue(orchestration.graphify_update_enabled)
        self.assertEqual(orchestration.graphify_executable, "graphify")
        self.assertTrue(orchestration.supabase_db_push_enabled)
        self.assertEqual(orchestration.supabase_executable, "supabase")

    def test_loads_target_branch_and_primary_branch_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            target_path = Path(directory) / "target.toml"
            target_path.write_text('target_branch = "develop"\nverification_commands = []\n', encoding="utf-8")
            alias_path = Path(directory) / "alias.toml"
            alias_path.write_text('primary_branch = "release"\nverification_commands = []\n', encoding="utf-8")

            self.assertEqual(load_orchestration_settings(target_path).primary_branch, "develop")
            self.assertEqual(load_orchestration_settings(alias_path).primary_branch, "release")

    def test_loads_coding_statistics_forecast_settings(self):
        root = Path(__file__).resolve().parents[1]
        statistics = load_coding_statistics_settings(
            root / "parameter_files" / "daedalus-tui-coding-statistics.toml"
        )

        self.assertEqual(statistics.recent_window_hours, 1)
        self.assertEqual(statistics.forecast_days, 7)
        self.assertEqual(statistics.thirty_day_forecast_days, 30)

    def test_loads_command_menu_settings(self):
        root = Path(__file__).resolve().parents[1]
        command_menu = load_command_menu_settings(
            root / "parameter_files" / "daedalus-tui-command-menu.toml"
        )

        self.assertEqual(command_menu.title, "Command Menu")
        self.assertEqual(command_menu.new_task_label, "New Task")
        self.assertEqual(command_menu.new_project_label, "New Project")
        self.assertEqual(command_menu.create_topic_label, "Create Topic")
        self.assertEqual(command_menu.personal_supabase_label, "Activate personal Supabase")
        self.assertEqual(command_menu.remove_personal_supabase_label, "Remove personal Supabase")
        self.assertEqual(command_menu.push_branch_label, "Push to GitHub")

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
