"""Provider-specific subprocess execution with normalized agent messages."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
from threading import Event, Lock, Thread
import time
from collections.abc import Sequence
from typing import Callable, Literal

from .debug_log import LOGGER, log_exception
from .environment import agent_environment


@dataclass(frozen=True)
class AgentLogEvent:
    kind: Literal["message", "error"]
    text: str


OutputCallback = Callable[[AgentLogEvent], None]


class _TimeoutTracker:
    """Track an inactivity deadline that agent stdout can refresh."""

    def __init__(self, timeout_seconds: float):
        self._timeout_seconds = timeout_seconds
        self._deadline = time.monotonic() + timeout_seconds
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._deadline = time.monotonic() + self._timeout_seconds

    def expired(self) -> bool:
        with self._lock:
            return time.monotonic() >= self._deadline

REASONING_MAP = {
    "light": "low",
    "medium": "medium",
    "high": "high",
    "extra-high": "xhigh",
    "max": "max",
}

# Executable and display name for each supported provider CLI.
PROVIDER_EXECUTABLES = {
    "codex": ("codex", "Codex CLI"),
    "cursor": ("agent", "Cursor CLI"),
    "claude": ("claude", "Claude Code CLI"),
}

# Shown when a provider exits without usable diagnostics, which is what an
# unauthenticated CLI usually looks like from here.
SIGN_IN_HINTS = {
    "codex": "Codex authentication: run `codex login` to sign in to your account.",
    "cursor": "Cursor authentication: run `agent login` or set CURSOR_API_KEY in .env.",
    "claude": "Claude Code authentication: run `claude auth login` to sign in to your account.",
}


@dataclass(frozen=True)
class ProviderAuthPolicy:
    """How provider CLI subprocesses authenticate.

    In account mode the runner removes each provider's API-key variables from
    the subprocess environment so the CLI falls back to its signed-in account
    and bills the operator's plan. ``api_key_variables`` holds variable names
    only; no key ever passes through this object.
    """

    account_login: bool = True
    api_key_variables: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def stripped_variables(self, provider: str) -> tuple[str, ...]:
        if not self.account_login:
            return ()
        return self.api_key_variables.get(provider, ())


@dataclass(frozen=True)
class AgentRequest:
    prompt: str
    directory: Path
    provider: str
    model: str
    reasoning: str
    writable_directories: tuple[Path, ...] = field(default_factory=tuple)
    environment_files: tuple[Path, ...] = field(default_factory=tuple)
    control: "AgentControl | None" = None
    timeout_seconds: float | None = None
    # Extra Claude Code permission rules for this run, such as the project's
    # verification commands; merged with the runner's configured allowlist.
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)
    settings_file: Path | None = None


@dataclass
class AgentControl:
    """Cooperative stop signals shared by a task and its active subprocess."""

    pause_requested: Event = field(default_factory=Event)
    cancel_requested: Event = field(default_factory=Event)
    # A non-destructive stop: the run ends, its worktree, branch, and files
    # stay exactly as they are, and the task remains continuable.
    interrupt_requested: Event = field(default_factory=Event)

    def request_pause(self) -> None:
        self.pause_requested.set()

    def request_cancel(self) -> None:
        self.cancel_requested.set()

    def request_interrupt(self) -> None:
        self.interrupt_requested.set()

    def clear_pause(self) -> None:
        self.pause_requested.clear()

    def clear_interrupt(self) -> None:
        self.interrupt_requested.clear()

    @property
    def stop_reason(self) -> str | None:
        if self.cancel_requested.is_set():
            return "cancelled"
        if self.interrupt_requested.is_set():
            return "interrupted"
        if self.pause_requested.is_set():
            return "paused"
        return None


@dataclass(frozen=True)
class AgentResult:
    provider: str
    returncode: int | None
    output: str = ""
    error: str | None = None
    stderr: str = ""
    stopped_reason: str | None = None
    tokens_consumed: int | None = None
    output_streamed: bool = False
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and self.error is None


class AgentRunner:
    """Run Codex, Claude Code, or Cursor and emit only assistant-facing messages."""

    def __init__(
        self,
        auth_policy: ProviderAuthPolicy | None = None,
        claude_permission_mode: str = "acceptEdits",
        claude_allowed_tools: Sequence[str] = (),
    ):
        self.auth_policy = auth_policy or ProviderAuthPolicy()
        self.claude_permission_mode = claude_permission_mode
        self.claude_allowed_tools = tuple(claude_allowed_tools)

    def command_for(self, request: AgentRequest) -> list[str]:
        if request.provider == "codex":
            reasoning = REASONING_MAP.get(request.reasoning, request.reasoning)
            command = [
                "codex",
                "exec",
                "-m",
                request.model,
                "-c",
                f'model_reasoning_effort="{reasoning}"',
                "--sandbox",
                "workspace-write",
            ]
            for directory in request.writable_directories:
                command.extend(["--add-dir", str(directory)])
            command.extend(["--json", request.prompt])
            return command

        if request.provider == "claude":
            command = [
                "claude",
                "--print",
                "--output-format",
                "stream-json",
                "--verbose",
            ]
            if request.settings_file is not None:
                command.extend(["--settings", str(request.settings_file)])
            # The worktree is already the working directory; only genuinely
            # extra roots need --add-dir. Its argument is variadic, so a
            # single-argument option always follows it and terminates the list
            # before the trailing prompt can be absorbed.
            for directory in request.writable_directories:
                if directory != request.directory:
                    command.extend(["--add-dir", str(directory)])
            # --allowedTools is variadic too, so it must also be followed by a
            # single-argument option before the prompt.
            allowed_tools = self.allowed_tools_for(request)
            if allowed_tools:
                command.extend(["--allowedTools", *allowed_tools])
            command.extend(["--model", request.model])
            effort = REASONING_MAP.get(request.reasoning, request.reasoning)
            if effort:
                command.extend(["--effort", effort])
            command.extend(["--permission-mode", self.claude_permission_mode])
            command.append(request.prompt)
            return command

        if request.provider == "cursor":
            return [
                "agent",
                "-p",
                "--output-format",
                "stream-json",
                "--force",
                request.prompt,
            ]

        raise ValueError(f"Unsupported agent provider: {request.provider}")

    def allowed_tools_for(self, request: AgentRequest) -> tuple[str, ...]:
        """Merge the configured Claude allowlist with per-run rules, in order, without duplicates."""
        merged: list[str] = []
        for rule in (*self.claude_allowed_tools, *request.allowed_tools):
            if rule and rule not in merged:
                merged.append(rule)
        return tuple(merged)

    def run(self, request: AgentRequest, on_output: OutputCallback) -> AgentResult:
        executable, name = PROVIDER_EXECUTABLES.get(request.provider, ("agent", "Cursor CLI"))
        if shutil.which(executable) is None:
            LOGGER.error("Agent executable unavailable provider=%s executable=%s", request.provider, executable)
            return AgentResult(
                provider=request.provider,
                returncode=None,
                error=f"{name} is unavailable. Install it so `{executable}` is on PATH.",
            )

        stripped = self.auth_policy.stripped_variables(request.provider)
        environment = agent_environment(
            request.provider,
            request.directory,
            request.environment_files,
            stripped,
        )
        if stripped:
            LOGGER.info(
                "Running provider=%s with account login; removed %s from the agent environment",
                request.provider,
                ", ".join(stripped),
            )
        try:
            command = self.command_for(request)
            LOGGER.info(
                "Launching agent provider=%s directory=%s timeout=%s prompt_length=%d",
                request.provider,
                request.directory,
                request.timeout_seconds,
                len(request.prompt),
            )
            process = subprocess.Popen(
                command,
                cwd=request.directory,
                # The agent is non-interactive: its prompt is supplied on the
                # command line. Do not let a child CLI share the Textual
                # terminal, where a terminal-mode change or input read can
                # make the parent UI appear to vanish.
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                shell=False,
                start_new_session=True,
                **({"env": environment} if environment is not None else {}),
            )
        except FileNotFoundError:
            LOGGER.exception("Agent executable disappeared before launch provider=%s", request.provider)
            return AgentResult(
                provider=request.provider,
                returncode=None,
                error=f"{name} is unavailable. Install it so `{executable}` is on PATH.",
            )
        except OSError as error:
            log_exception(f"Could not launch {name}", error)
            return AgentResult(
                provider=request.provider,
                returncode=None,
                error=f"{name} could not be started: {error}",
            )

        LOGGER.info("Agent process started provider=%s pid=%s", request.provider, getattr(process, "pid", None))

        output: dict[str, list[str]] = {"stdout": [], "stderr": []}
        messages: list[str] = []
        timeout_tracker = (
            _TimeoutTracker(request.timeout_seconds)
            if request.timeout_seconds is not None
            else None
        )
        threads = [
            self._stream_stdout(
                process.stdout,
                request.provider,
                output,
                messages,
                on_output,
                timeout_tracker.reset if timeout_tracker is not None else None,
            ),
            self._stream(process.stderr, "stderr", output),
        ]
        stopped_reason, timed_out = self._wait_for_process(process, request.control, timeout_tracker)
        returncode = process.returncode
        for thread in threads:
            # A CLI descendant can inherit a pipe and keep a reader blocked
            # after the direct child has been terminated. Reader threads are
            # daemonized, so never let that pipe prevent task shutdown.
            thread.join(timeout=2)
            if thread.is_alive():
                LOGGER.warning("Agent pipe reader did not finish provider=%s thread=%s", request.provider, thread.name)

        stdout = "".join(output["stdout"])
        stderr = "".join(output["stderr"])
        if timed_out:
            LOGGER.warning("Agent timed out provider=%s pid=%s", request.provider, getattr(process, "pid", None))
            timeout = request.timeout_seconds
            timeout_text = f" after {timeout:g} seconds" if timeout is not None else ""
            return AgentResult(
                provider=request.provider,
                returncode=returncode,
                output=stdout,
                error=(
                    f"{name} timed out{timeout_text} while waiting for a response. "
                    "The agent may be offline or unable to reach its service. "
                    "Check your internet connection and retry."
                ),
                stderr=stderr,
                timed_out=True,
            )
        if returncode == 0:
            LOGGER.info("Agent process completed provider=%s pid=%s", request.provider, getattr(process, "pid", None))
            normalized = self._normalize_output(request.provider, stdout, stderr)
            tokens_consumed = self._extract_token_usage(request.provider, stdout)
            if normalized[1] is not None:
                return AgentResult(
                    request.provider,
                    returncode,
                    stdout,
                    normalized[1],
                    stderr,
                    stopped_reason,
                    tokens_consumed,
                    bool(messages),
                )
            if request.provider == "codex":
                return AgentResult(
                    request.provider,
                    returncode,
                    "\n\n".join(messages),
                    None,
                    stderr,
                    stopped_reason,
                    tokens_consumed,
                )
            if request.provider == "claude":
                # Claude Code streams whole assistant blocks, so the transcript
                # is already complete; the final result payload is only a
                # fallback for a run that emitted no assistant text.
                return AgentResult(
                    request.provider,
                    returncode,
                    "\n\n".join(messages) if messages else normalized[0],
                    None,
                    stderr,
                    stopped_reason,
                    tokens_consumed,
                    bool(messages),
                )
            return AgentResult(
                request.provider,
                returncode,
                normalized[0],
                None,
                stderr,
                stopped_reason,
                tokens_consumed,
                bool(messages),
            )

        if stopped_reason:
            LOGGER.info("Agent process stopped provider=%s reason=%s", request.provider, stopped_reason)
            return AgentResult(
                request.provider,
                returncode,
                stdout,
                None,
                stderr,
                stopped_reason,
            )

        diagnostics = self._failure_diagnostics(request.provider, stdout, stderr)
        LOGGER.error("Agent process failed provider=%s returncode=%s", request.provider, returncode)
        if self._sign_in_hint_applies(request.provider, environment, stripped):
            diagnostics += "\n\n" + SIGN_IN_HINTS[request.provider]
        return AgentResult(
            provider=request.provider,
            returncode=returncode,
            error=(
                f"{name} failed with exit code {returncode}."
                + f"\n\nDiagnostics:\n{diagnostics}"
            ).strip(),
            stderr=stderr,
        )

    @staticmethod
    def _sign_in_hint_applies(
        provider: str,
        environment: dict[str, str] | None,
        stripped: tuple[str, ...],
    ) -> bool:
        """Add sign-in guidance when no usable credential could have been present."""
        if provider not in SIGN_IN_HINTS:
            return False
        if stripped:
            # Account mode removed the API keys on purpose, so a failure here is
            # most often an account that is not signed in.
            return True
        if provider == "cursor":
            return not (environment or {}).get("CURSOR_API_KEY", "").strip()
        return False

    @staticmethod
    def _wait_for_process(
        process,
        control: AgentControl | None,
        timeout_tracker: _TimeoutTracker | None = None,
    ) -> tuple[str | None, bool]:
        if control is None and timeout_tracker is None:
            process.wait()
            return None, False
        while True:
            returncode = process.poll()
            if returncode is not None:
                return None, False
            reason = control.stop_reason if control is not None else None
            if reason:
                LOGGER.info("Stopping agent process reason=%s pid=%s", reason, getattr(process, "pid", None))
                AgentRunner._terminate_process(process)
                return reason, False
            if timeout_tracker is not None and timeout_tracker.expired():
                LOGGER.warning("Agent process deadline reached pid=%s", getattr(process, "pid", None))
                AgentRunner._terminate_process(process)
                return None, True
            time.sleep(0.05)

    @staticmethod
    def _terminate_process(process) -> None:
        pid = getattr(process, "pid", None)
        try:
            if isinstance(pid, int) and os.name == "posix":
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            else:
                process.terminate()
        except (AttributeError, OSError, ProcessLookupError):
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            LOGGER.warning("Agent process ignored termination pid=%s; killing process group", pid)
            try:
                if isinstance(pid, int) and os.name == "posix":
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                else:
                    process.kill()
            except (AttributeError, OSError, ProcessLookupError):
                process.kill()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                LOGGER.error("Agent process remained alive after SIGKILL pid=%s", pid)

    @staticmethod
    def _stream_stdout(
        stream,
        provider: str,
        output: dict[str, list[str]],
        messages: list[str],
        callback: OutputCallback,
        on_activity: Callable[[], None] | None = None,
    ) -> Thread:
        parser = AgentRunner.event_parser(provider)

        def forward() -> None:
            if stream is None:
                return
            for chunk in iter(stream.readline, ""):
                if not chunk:
                    continue
                output["stdout"].append(chunk)
                if on_activity is not None:
                    on_activity()
                if parser is None:
                    continue
                message = parser(chunk)
                if message:
                    messages.append(message)
                    AgentRunner._forward_event(callback, AgentLogEvent("message", message))
            stream.close()

        thread = Thread(target=forward, daemon=True)
        thread.start()
        return thread

    @staticmethod
    def _forward_event(callback: OutputCallback, event: AgentLogEvent) -> None:
        try:
            callback(event)
        except Exception as error:
            # UI delivery must never strand the subprocess reader or executor.
            log_exception("Agent output callback failed", error)

    @staticmethod
    def _stream(stream, channel: str, output: dict[str, list[str]]) -> Thread:
        def forward() -> None:
            if stream is None:
                return
            for chunk in iter(stream.readline, ""):
                if chunk:
                    output[channel].append(chunk)
            stream.close()

        thread = Thread(target=forward, daemon=True)
        thread.start()
        return thread

    @staticmethod
    def parse_codex_event(line: str) -> str | None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if payload.get("type") != "item.completed":
            return None
        item = payload.get("item")
        if not isinstance(item, dict) or item.get("type") != "agent_message":
            return None
        text = item.get("text")
        return text.strip() if isinstance(text, str) and text.strip() else None

    @staticmethod
    def event_parser(provider: str) -> Callable[[str], str | None] | None:
        """Return the stream-event parser for a provider, if it streams events."""
        return {
            "codex": AgentRunner.parse_codex_event,
            "cursor": AgentRunner.parse_cursor_event,
            "claude": AgentRunner.parse_claude_event,
        }.get(provider)

    @staticmethod
    def parse_claude_event(line: str) -> str | None:
        """Return completed assistant text from Claude Code's stream-json events.

        Claude Code emits one event per assistant content block rather than
        token deltas, so each parsed message is a complete transcript entry.
        Tool-use blocks carry no text and are filtered out here.
        """
        text = AgentRunner.parse_cursor_event(line)
        return text.strip() if text and text.strip() else None

    @staticmethod
    def parse_cursor_event(line: str) -> str | None:
        """Return assistant text deltas from Cursor's stream-json events."""
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if payload.get("type") != "assistant":
            return None
        message = payload.get("message")
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
            )
        else:
            return None
        return text if text.strip() else None

    @staticmethod
    def _normalize_output(provider: str, stdout: str, stderr: str) -> tuple[str, str | None]:
        if provider == "claude":
            # Claude Code's transcript comes from streamed assistant events, so a
            # missing result payload is not an error the way it is for Cursor.
            return AgentRunner._result_text(stdout) or stdout, None
        if provider != "cursor":
            return stdout, None
        payloads = AgentRunner._json_payloads(stdout)
        if not payloads:
            return stdout, "Cursor returned malformed JSON.\n\nSTDERR:\n" + stderr
        result = next(
            (
                payload.get("result")
                for payload in reversed(payloads)
                if isinstance(payload.get("result"), str)
            ),
            None,
        )
        if not isinstance(result, str):
            return stdout, "Cursor returned JSON without a result.\n\nSTDERR:\n" + stderr
        return result, None

    @staticmethod
    def _result_text(stdout: str) -> str | None:
        """Return the last `result` string emitted on a stream-json stdout."""
        return next(
            (
                payload.get("result")
                for payload in reversed(AgentRunner._json_payloads(stdout))
                if isinstance(payload.get("result"), str)
            ),
            None,
        )

    @staticmethod
    def _json_payloads(stdout: str) -> list[dict]:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payloads = []
            for line in stdout.splitlines():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    payloads.append(value)
            return payloads
        return [payload] if isinstance(payload, dict) else []

    @staticmethod
    def _extract_token_usage(provider: str, stdout: str) -> int | None:
        payloads = AgentRunner._json_payloads(stdout)
        if provider == "codex":
            payloads = [payload for payload in payloads if payload.get("type") == "turn.completed"]
        elif any(payload.get("type") == "result" for payload in payloads):
            payloads = [payload for payload in payloads if payload.get("type") == "result"]

        for payload in reversed(payloads):
            usage = payload.get("usage")
            if not isinstance(usage, dict) and any(
                key in payload
                for key in (
                    "total_tokens",
                    "totalTokens",
                    "input_tokens",
                    "inputTokens",
                    "output_tokens",
                    "outputTokens",
                )
            ):
                usage = payload
            if isinstance(usage, dict):
                tokens = AgentRunner._tokens_from_usage(usage)
                if tokens is not None:
                    return tokens
        return None

    @staticmethod
    def _tokens_from_usage(usage: dict) -> int | None:
        for key in ("total_tokens", "totalTokens", "total", "tokens"):
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return max(0, value)

        input_tokens = AgentRunner._first_integer(
            usage, "input_tokens", "inputTokens", "prompt_tokens", "promptTokens"
        )
        output_tokens = AgentRunner._first_integer(
            usage,
            "output_tokens",
            "outputTokens",
            "completion_tokens",
            "completionTokens",
            "reasoning_output_tokens",
            "reasoningOutputTokens",
        )
        # Claude Code reports cached prompt tokens separately from input_tokens;
        # leaving them out would undercount a cached run by most of its prompt.
        cached_tokens = sum(
            max(0, value)
            for key in ("cache_read_input_tokens", "cache_creation_input_tokens")
            if isinstance(value := usage.get(key), int) and not isinstance(value, bool)
        )
        if input_tokens is None and output_tokens is None and not cached_tokens:
            return None
        return max(0, input_tokens or 0) + max(0, output_tokens or 0) + cached_tokens

    @staticmethod
    def _first_integer(payload: dict, *keys: str) -> int | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        return None

    @staticmethod
    def _failure_diagnostics(provider: str, stdout: str, stderr: str) -> str:
        if stderr.strip():
            return stderr.strip()
        if provider == "claude":
            result = AgentRunner._result_text(stdout)
            return (result or stdout).strip() or "No diagnostics were emitted."
        if provider == "cursor":
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                for key in ("error", "message", "result"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
            if stdout.strip():
                return stdout.strip()
            return "No diagnostics were emitted. Check Cursor authentication (CURSOR_API_KEY or `agent login`)."
        return stdout.strip() or "No diagnostics were emitted."
