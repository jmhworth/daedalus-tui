"""The shipped parameter file's usage-command settings reach the monitor."""

from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

from tui.config import load_tui_settings


ROOT = Path(__file__).resolve().parents[1]


class UsageCommandSettingsTests(unittest.TestCase):
    def test_the_shipped_parameters_give_both_providers_usage_commands(self):
        """The bar is only right when it can ask the CLIs, so they ship configured."""
        usage = load_tui_settings().usage
        for name in ("claude", "codex"):
            provider = usage.providers[name]
            commands = provider.resolved_commands()
            self.assertTrue(commands, f"{name} has no usage command configured")
            self.assertTrue(provider.use_pty, f"{name} must run under a terminal")
            self.assertTrue(provider.fallback_to_local)
            self.assertTrue(all(command[0] == name for command in commands))

    def test_the_shipped_commands_override_each_cli_permission_prompt(self):
        """A usage command that stops at a prompt produces nothing before the timeout."""
        usage = load_tui_settings().usage
        for command in usage.providers["claude"].resolved_commands():
            self.assertIn("--permission-mode", command)
            self.assertIn("bypassPermissions", command)
        for command in usage.providers["codex"].resolved_commands():
            self.assertIn("--ask-for-approval", command)
            self.assertIn("never", command)

    def test_provider_command_overrides_are_read_from_the_parameter_file(self):
        original = (ROOT / "parameter_files" / "daedalus-tui.toml").read_text(encoding="utf-8")
        override = textwrap.dedent(
            """
            [usage.claude]
            label = "Claude"
            commands = [["my-usage", "--json"], ["my-usage", "--text"]]
            use_pty = false
            input_text = "/usage\\r"
            fallback_to_local = false
            env = { USAGE_PLAIN = "1" }
            """
        )
        # Replace the shipped Claude provider table with the override, keeping
        # the rest of the file so the whole document still validates.
        start = original.index("[usage.claude]")
        end = original.index("[usage.codex]")
        patched = original[:start] + override.strip() + "\n\n" + original[end:]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daedalus-tui.toml"
            path.write_text(patched, encoding="utf-8")
            provider = load_tui_settings(path).usage.providers["claude"]

        self.assertEqual(
            provider.resolved_commands(),
            (("my-usage", "--json"), ("my-usage", "--text")),
        )
        self.assertFalse(provider.use_pty)
        self.assertEqual(provider.input_text, "/usage\r")
        self.assertFalse(provider.fallback_to_local)
        self.assertEqual(provider.env, {"USAGE_PLAIN": "1"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
