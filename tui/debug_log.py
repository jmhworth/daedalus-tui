"""Persistent diagnostics for failures that occur after the Textual screen closes."""

from __future__ import annotations

import faulthandler
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import threading


LOGGER = logging.getLogger("daedalus.tui")
LOGGER.addHandler(logging.NullHandler())
_HANDLER_NAME = "daedalus-debug-file"
_thread_hook_installed = False


def configure_debug_logging(path: Path) -> Path:
    """Write detailed runtime diagnostics to a rotating local log file."""
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.propagate = False
    for handler in tuple(LOGGER.handlers):
        if handler.get_name() == _HANDLER_NAME:
            LOGGER.removeHandler(handler)
            handler.close()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        return path
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)s [%(threadName)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    LOGGER.addHandler(handler)
    LOGGER.info("Debug logging initialized at %s", path)
    _install_thread_exception_logging()
    return path


def install_fault_handler(path: Path):
    """Capture fatal faults and ``SIGUSR1`` thread dumps in the debug log."""
    try:
        trace_file = path.open("a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=trace_file, all_threads=True)
        if hasattr(signal, "SIGUSR1"):
            faulthandler.register(signal.SIGUSR1, file=trace_file, all_threads=True)
        LOGGER.info("Fault handler enabled; send SIGUSR1 to dump all thread stacks.")
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
    LOGGER.error(message, exc_info=(type(error), error, error.__traceback__))


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
