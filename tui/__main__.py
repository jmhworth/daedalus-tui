from .app import DaedalusTuiApp, install_signal_guards
from .debug_log import LOGGER, log_exception


def main() -> None:
    app = DaedalusTuiApp()
    # Before app.run(): asyncio.run only installs its task-cancelling SIGINT
    # handler when it finds the default one, and that handler is what turned
    # a stray SIGINT into a silent exit with no return code and no unmount.
    install_signal_guards(app)
    try:
        app.run()
    except BaseException as error:
        log_exception("Textual run loop raised", error)
        app.shutdown_after_run()
        raise
    return_code = getattr(app, "return_code", None)
    if return_code not in (None, 0):
        LOGGER.error(
            "Textual run loop returned with failure code=%s debug_log=%s",
            return_code,
            getattr(app, "debug_log_path", None),
        )
    elif not getattr(app, "_textual_unmounted", False):
        LOGGER.error(
            "Textual run loop returned without unmount return_code=%s debug_log=%s",
            return_code,
            getattr(app, "debug_log_path", None),
        )
    app.shutdown_after_run()


if __name__ == "__main__":
    main()
