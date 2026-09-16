"""Persistent diagnostics for failures that occur after the Textual screen closes.

The runtime log lives under the shared ``errors/`` folder (``daedalus.log``),
fault-handler output has its own file (``faults.log``) because the fault
handler keeps a raw file descriptor that a rotating handler would leave
pointing at a rotated-away file, and each agent run can append its complete
diagnostics to a per-run file before the UI truncates them for display.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import faulthandler
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import signal
import sys
import threading
from threading import Lock


LOGGER = logging.getLogger("daedalus.tui")
LOGGER.addHandler(logging.NullHandler())
_HANDLER_NAME = "daedalus-debug-file"
_thread_hook_installed = False
_status_lock = Lock()
_run_log_failures: set[Path] = set()

DEFAULT_LOG_MAX_BYTES = 2_000_000
DEFAULT_LOG_BACKUP_COUNT = 3

# Known credential shapes. The replacement keeps the variable name so a
# diagnostic still says *which* key was involved without revealing it.
_CREDENTIAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 [redacted]"),
    (
        re.compile(
            r"(?i)\b([A-Z0-9_]*(?:API_KEY|AUTH_TOKEN|SECRET|PASSWORD|ACCESS_TOKEN|PRIVATE_KEY)[A-Z0-9_]*)"
            r"\s*[=:]\s*['\"]?([^\s'\"]{4,})"
        ),
        r"\1=[redacted]",
    ),
    (re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{12,}"), "sk-[redacted]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "gh*_[redacted]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA[redacted]"),
    (re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}"), "xox*-[redacted]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[redacted-jwt]"),
)


@dataclass(frozen=True)
class LoggingStatus:
    """Where diagnostics are written and whether the log could be opened."""

    path: Path
    fault_path: Path | None = None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.error is None


def scrub_credentials(text: str) -> str:
    """Remove known credential patterns while keeping the surrounding failure text."""
    if not text:
        return text
    scrubbed = text
    for pattern, replacement in _CREDENTIAL_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


class _QuietRotatingFileHandler(RotatingFileHandler):
    """A rotating handler that reports its own write failure once, then detaches.

    Python's default ``handleError`` prints every failed emit to stderr. On a
    full disk or a directory that became read-only that would repeat on every
    log call and could recurse through the logger itself, so the handler
    records the failure, tells the user once, and removes itself.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.failure: str | None = None

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802 - logging API
        error = sys.exc_info()[1]
        self.failure = f"{self.baseFilename}: {error}"
        try:
            LOGGER.removeHandler(self)
            self.close()
        except Exception:
            pass
        try:
            print(
                f"Daedalus TUI could not write its diagnostics log ({self.failure}); "
                "further diagnostics stay in memory only.",
                file=sys.stderr,
                flush=True,
            )
        except Exception:
            pass


def configure_debug_logging(
    path: Path,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> LoggingStatus:
    """Write detailed runtime diagnostics to a rotating local log file.

    Returns a :class:`LoggingStatus` naming the exact path. When the file cannot
    be opened the error is reported in the status (and once on stderr) and the
    logger keeps only its in-memory null handler; nothing claims the log exists.
    """
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.propagate = False
    for handler in tuple(LOGGER.handlers):
        if handler.get_name() == _HANDLER_NAME:
            LOGGER.removeHandler(handler)
            handler.close()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = _QuietRotatingFileHandler(
            path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
    except OSError as error:
        message = f"{path}: {error}"
        try:
            print(
                f"Daedalus TUI could not open its diagnostics log ({message}); "
                "diagnostics stay in memory only.",
                file=sys.stderr,
                flush=True,
            )
        except Exception:
            pass
        return LoggingStatus(path, None, message)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03dZ %(levelname)s [%(threadName)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.formatter.converter = _utc_converter
    LOGGER.addHandler(handler)
    LOGGER.info("Debug logging initialized at %s", path)
    _install_thread_exception_logging()
    return LoggingStatus(path)


def _utc_converter(timestamp: float | None):
    return datetime.fromtimestamp(timestamp or 0, timezone.utc).timetuple()


def logging_status(path: Path) -> LoggingStatus:
    """Return the status of the configured file handler, if any."""
    for handler in LOGGER.handlers:
        if handler.get_name() == _HANDLER_NAME:
            failure = getattr(handler, "failure", None)
            return LoggingStatus(path, None, failure)
    return LoggingStatus(path, None, "logging is not configured")


def install_fault_handler(path: Path):
    """Capture fatal faults and ``SIGUSR1`` thread dumps in a dedicated file.

    The fault handler retains an open descriptor, so it must not share a
    rotating file: after rotation its dumps would land in the renamed backup.
    The file is (re)opened only here, at startup, which is the one moment that
    is safe.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        trace_file = path.open("a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=trace_file, all_threads=True)
        if hasattr(signal, "SIGUSR1"):
            faulthandler.register(signal.SIGUSR1, file=trace_file, all_threads=True)
        LOGGER.info("Fault handler enabled at %s; send SIGUSR1 to dump all thread stacks.", path)
        return trace_file
    except (OSError, RuntimeError):
        LOGGER.exception("Could not enable fault handler for %s", path)
        return None


def close_fault_handler(trace_file) -> None:
    if trace_file is None:
        return
    try:
        if hasattr(signal, "SIGUSR1"):
            faulthandler.unregister(signal.SIGUSR1)
        faulthandler.disable()
        trace_file.close()
    except (OSError, RuntimeError):
        LOGGER.exception("Could not close fault handler")


def log_exception(message: str, error: BaseException) -> None:
    LOGGER.error(scrub_credentials(message), exc_info=(type(error), error, error.__traceback__))


def format_context(**context: object) -> str:
    """Render task/run context fields in a stable ``key=value`` order."""
    ordered = (
        "project",
        "task",
        "turn",
        "run",
        "phase",
        "provider",
        "exit_status",
    )
    parts = [f"{key}={context[key]}" for key in ordered if context.get(key) not in (None, "")]
    parts.extend(
        f"{key}={value}" for key, value in context.items() if key not in ordered and value not in (None, "")
    )
    return " ".join(parts)


def log_event(level: int, message: str, *, error: BaseException | None = None, **context: object) -> None:
    """Log one structured lifecycle event with task, turn, run, and phase context."""
    prefix = format_context(**context)
    text = scrub_credentials(f"{prefix} | {message}" if prefix else message)
    if error is not None:
        LOGGER.log(level, text, exc_info=(type(error), error, error.__traceback__))
    else:
        LOGGER.log(level, text)


def append_run_diagnostic(
    path: Path,
    severity: str,
    text: str,
    *,
    max_bytes: int = 1_000_000,
    **context: object,
) -> bool:
    """Append one complete diagnostic block to a per-run file before UI truncation.

    Returns ``False`` when the file cannot be written; that failure is logged
    once per path and never retried recursively. When the file would exceed
    ``max_bytes`` its oldest content is dropped so the newest diagnostics stay
    complete.
    """
    stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    header = f"=== {stamp} {severity.upper()} {format_context(**context)}".rstrip()
    block = f"{header}\n{scrub_credentials(text).rstrip()}\n\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(block)
        if path.stat().st_size > max_bytes:
            _trim_head(path, max_bytes)
    except OSError as error:
        with _status_lock:
            first_failure = path not in _run_log_failures
            _run_log_failures.add(path)
        if first_failure:
            LOGGER.error("Could not write run diagnostics file %s: %s", path, error)
        return False
    with _status_lock:
        _run_log_failures.discard(path)
    return True


def _trim_head(path: Path, max_bytes: int) -> None:
    """Keep the newest ``max_bytes`` of a diagnostics file, cut at a block boundary."""
    data = path.read_bytes()
    if len(data) <= max_bytes:
        return
    tail = data[-max_bytes:]
    boundary = tail.find(b"\n=== ")
    if boundary >= 0:
        tail = tail[boundary + 1 :]
    marker = f"[… older diagnostics trimmed to keep this file under {max_bytes:,} bytes …]\n\n".encode("utf-8")
    temporary = path.with_name(f".{path.name}.trim")
    temporary.write_bytes(marker + tail)
    os.replace(temporary, path)


def _install_thread_exception_logging() -> None:
    global _thread_hook_installed
    if _thread_hook_installed:
        return
    original_hook = threading.excepthook

    def log_thread_exception(args: threading.ExceptHookArgs) -> None:
        LOGGER.error(
            "Unhandled exception in thread %s",
            args.thread.name if args.thread is not None else "unknown",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        original_hook(args)

    threading.excepthook = log_thread_exception
    _thread_hook_installed = True


__all__ = [
    "LOGGER",
    "LoggingStatus",
    "append_run_diagnostic",
    "close_fault_handler",
    "configure_debug_logging",
    "format_context",
    "install_fault_handler",
    "log_event",
    "log_exception",
    "logging_status",
    "scrub_credentials",
]
