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
from typing import Callable, Literal

from .debug_log import LOGGER, log_exception
from .environment import cursor_environment, with_agent_credential_fallbacks


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
    credential_files: tuple[Path, ...] = field(default_factory=tuple)


@dataclass
class AgentControl:
    """Cooperative stop signals shared by a task and its active subprocess."""

    pause_requested: Event = field(default_factory=Event)
    cancel_requested: Event = field(default_factory=Event)

    def request_pause(self) -> None:
        self.pause_requested.set()

    def request_cancel(self) -> None:
        self.cancel_requested.set()

    def clear_pause(self) -> None:
        self.pause_requested.clear()

    @property
    def stop_reason(self) -> str | None:
        if self.cancel_requested.is_set():
            return "cancelled"
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
    """Run Codex or Cursor directly and emit only assistant-facing messages."""

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

    def run(self, request: AgentRequest, on_output: OutputCallback) -> AgentResult:
        executable = "codex" if request.provider == "codex" else "agent"
        name = "Codex CLI" if request.provider == "codex" else "Cursor CLI"
        if shutil.which(executable) is None:
            LOGGER.error("Agent executable unavailable provider=%s executable=%s", request.provider, executable)
            return AgentResult(
                provider=request.provider,
                returncode=None,
                error=f"{name} is unavailable. Install it so `{executable}` is on PATH.",
            )

        environment = None
        if request.provider == "cursor":
            environment = with_agent_credential_fallbacks(
                cursor_environment(request.directory, request.environment_files),
                request.credential_files,
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
        if request.provider == "cursor" and not environment.get("CURSOR_API_KEY", "").strip():
            diagnostics += (
                "\n\nCursor authentication: run `agent login`, or set CURSOR_API_KEY once in "
                "the launch-root `.env` (or the Daedalus TUI package `.env`). "
                "Target projects do not need their own copy."
            )
        return AgentResult(
            provider=request.provider,
            returncode=returncode,
            error=(
                f"{request.provider.capitalize()} failed with exit code {returncode}."
                + f"\n\nDiagnostics:\n{diagnostics}"
            ).strip(),
            stderr=stderr,
        )

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
        def forward() -> None:
            if stream is None:
                return
            for chunk in iter(stream.readline, ""):
                if not chunk:
                    continue
                output["stdout"].append(chunk)
                if on_activity is not None:
                    on_activity()
                if provider == "codex":
                    message = AgentRunner.parse_codex_event(chunk)
                    if message:
                        messages.append(message)
                        AgentRunner._forward_event(callback, AgentLogEvent("message", message))
                elif provider == "cursor":
                    message = AgentRunner.parse_cursor_event(chunk)
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
        if input_tokens is None and output_tokens is None:
            return None
        return max(0, input_tokens or 0) + max(0, output_tokens or 0)

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
            return (
                "No diagnostics were emitted. Check Cursor authentication "
                "(launch-root/package CURSOR_API_KEY or `agent login`)."
            )
        return stdout.strip() or "No diagnostics were emitted."
