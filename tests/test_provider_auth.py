import subprocess
import unittest
from unittest.mock import patch

from tui.config import ProviderAuthSettings
from tui.provider_auth import check_provider_auth, sign_in_instructions


class CompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


CLAUDE = ProviderAuthSettings(
    label="Claude Code",
    api_key_variables=("ANTHROPIC_API_KEY",),
    status_command=("claude", "auth", "status"),
    sign_in_command=("claude", "auth", "login"),
)


class ProviderAuthTests(unittest.TestCase):
    def test_reports_a_signed_in_account(self):
        with patch("tui.provider_auth.shutil.which", return_value="/usr/bin/claude"):
            status = check_provider_auth(
                "claude",
                CLAUDE,
                run_process=lambda *a, **k: CompletedProcess(0, "Logged in as operator"),
            )

        self.assertTrue(status.signed_in)
        self.assertIn("signed in", status.summary)
        self.assertIn("Logged in as operator", status.detail)

    def test_reports_a_signed_out_account_with_the_login_command(self):
        with patch("tui.provider_auth.shutil.which", return_value="/usr/bin/claude"):
            status = check_provider_auth(
                "claude",
                CLAUDE,
                run_process=lambda *a, **k: CompletedProcess(1, "", "Not logged in"),
            )

        self.assertFalse(status.signed_in)
        self.assertEqual(status.sign_in_hint, "claude auth login")
        self.assertIn("claude auth login", sign_in_instructions(status, account_login=True))

    def test_a_missing_cli_is_unknown_rather_than_signed_out(self):
        with patch("tui.provider_auth.shutil.which", return_value=None):
            status = check_provider_auth("claude", CLAUDE)

        self.assertIsNone(status.signed_in)
        self.assertFalse(status.executable_available)
        self.assertIn("not on PATH", status.detail)

    def test_a_timeout_is_unknown_rather_than_signed_out(self):
        def timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=15)

        with patch("tui.provider_auth.shutil.which", return_value="/usr/bin/claude"):
            status = check_provider_auth("claude", CLAUDE, run_process=timeout)

        self.assertIsNone(status.signed_in)
        self.assertIn("did not respond", status.detail)

    def test_a_provider_without_a_status_command_is_unknown(self):
        status = check_provider_auth("codex", ProviderAuthSettings(label="Codex"))

        self.assertIsNone(status.signed_in)
        self.assertIn("No status command", status.detail)

    def test_api_key_mode_explains_how_to_switch_to_account_login(self):
        with patch("tui.provider_auth.shutil.which", return_value="/usr/bin/claude"):
            status = check_provider_auth(
                "claude", CLAUDE, run_process=lambda *a, **k: CompletedProcess(0, "ok")
            )

        instructions = sign_in_instructions(status, account_login=False)
        self.assertIn("API-key mode", instructions)
        self.assertIn('auth.mode = "account"', instructions)


if __name__ == "__main__":
    unittest.main()
