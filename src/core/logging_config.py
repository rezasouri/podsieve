# logging_config.py

from __future__ import annotations

import atexit
import io
import logging
import logging.handlers
import os
import sys
import threading
import warnings
from pathlib import Path
from queue import Queue

from rich.console import Console
from rich.logging import RichHandler


_QUEUE_LISTENER: logging.handlers.QueueListener | None = None
_QUEUE_HANDLER: logging.Handler | None = None
_CONSOLE_HANDLER: logging.Handler | None = None
_FILE_HANDLER: logging.Handler | None = None
_CONFIGURED = False
_STDERR_CAPTURED = False
_STDERR_THREAD: threading.Thread | None = None

_CONSOLE_TIME_FORMAT = "[%H:%M:%S]"

_FILE_LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | "
    "%(process)d:%(threadName)s | "
    "%(pathname)s:%(lineno)d | %(funcName)s | "
    "%(message)s"
)

_FILE_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _logging_level(value: str | int) -> int:
    if isinstance(value, int):
        return value
    level = getattr(logging, value.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"unknown logging level: {value!r}")
    return level


def configure_logging(
    *,
    log_dir: str | Path = "logs",
    log_filename: str = "application.log",
    log_path: str | Path | None = None,
    console_level: str | int = "INFO",
    file_level: str | int = "INFO",
    backup_count: int = 14,
    capture_stderr: bool = False,
    force: bool = False,
) -> None:
    """
    Configure application logging.

    Features:
    - Colored console logs using Rich
    - Asynchronous file logging
    - Daily log rotation
    - Optional stderr capture for FFmpeg, Qt and native libraries
    """
    global _CONFIGURED, _QUEUE_LISTENER, _QUEUE_HANDLER, _CONSOLE_HANDLER, _FILE_HANDLER

    if _CONFIGURED and not force:
        return
    if _CONFIGURED and force:
        shutdown_logging()

    if log_path is not None:
        requested_path = Path(log_path).expanduser()
        log_directory = requested_path.parent.resolve()
        log_filename = requested_path.name
    else:
        log_directory = Path(log_dir).expanduser().resolve()
    log_directory.mkdir(parents=True, exist_ok=True)

    log_path = log_directory / log_filename

    # When stderr is captured, console logs must use stdout
    # to prevent an infinite logging loop.
    console_stream = sys.stdout if capture_stderr else sys.stderr

    console_handler = RichHandler(
        level=_logging_level(console_level),
        console=Console(file=console_stream),
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        omit_repeated_times=False,
        log_time_format=_CONSOLE_TIME_FORMAT,
        markup=False,
    )
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    log_queue: Queue = Queue(-1)

    queue_handler = logging.handlers.QueueHandler(log_queue)
    queue_handler.setLevel(_logging_level(file_level))

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path,
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setLevel(_logging_level(file_level))
    file_handler.setFormatter(
        logging.Formatter(
            fmt=_FILE_LOG_FORMAT,
            datefmt=_FILE_LOG_DATE_FORMAT,
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove handlers installed by frameworks or previous configurations.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(queue_handler)
    _CONSOLE_HANDLER = console_handler
    _QUEUE_HANDLER = queue_handler

    # Make existing loggers use the root logger.
    for logger in logging.root.manager.loggerDict.values():
        if not isinstance(logger, logging.Logger):
            continue

        for handler in list(logger.handlers):
            logger.removeHandler(handler)

        logger.propagate = True

    # Reduce noisy third-party logs if needed.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    logging.captureWarnings(True)
    warnings.simplefilter("default")

    _FILE_HANDLER = file_handler
    _QUEUE_LISTENER = logging.handlers.QueueListener(
        log_queue,
        file_handler,
        respect_handler_level=True,
    )
    _QUEUE_LISTENER.start()

    _CONFIGURED = True
    atexit.register(shutdown_logging)

    logger = logging.getLogger(__name__)
    logger.debug("Logging configured")
    logger.debug("Log file: %s", log_path)

    if capture_stderr:
        capture_stderr_to_logger()


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the specified module."""
    return logging.getLogger(name)


def capture_stderr_to_logger(
    *,
    logger_name: str = "stderr",
    level: int = logging.INFO,
) -> None:
    """
    Capture process stderr at the file-descriptor level.

    Useful for FFmpeg, Qt and native libraries that write directly to stderr.
    """
    global _STDERR_CAPTURED, _STDERR_THREAD

    if _STDERR_CAPTURED:
        return

    if not _CONFIGURED:
        raise RuntimeError(
            "Call configure_logging() before capture_stderr_to_logger()."
        )

    _STDERR_CAPTURED = True

    read_fd, write_fd = os.pipe()

    os.set_inheritable(read_fd, False)
    os.set_inheritable(write_fd, True)

    os.dup2(write_fd, 2)
    os.close(write_fd)

    sys.stderr = io.TextIOWrapper(
        os.fdopen(2, "wb", closefd=False),
        encoding="utf-8",
        errors="replace",
        line_buffering=True,
    )

    logger = logging.getLogger(logger_name)

    def drain_stderr() -> None:
        try:
            with os.fdopen(read_fd, "rb", closefd=True) as raw:
                with io.TextIOWrapper(
                    raw,
                    encoding="utf-8",
                    errors="replace",
                    newline="",
                ) as stream:
                    for line in stream:
                        text = line.rstrip("\r\n")

                        if text:
                            logger.log(level, text)

        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to capture stderr"
            )

    _STDERR_THREAD = threading.Thread(
        target=drain_stderr,
        name="stderr-logger",
        daemon=True,
    )
    _STDERR_THREAD.start()


def shutdown_logging() -> None:
    """Flush and close the asynchronous logging system."""
    global _QUEUE_LISTENER, _QUEUE_HANDLER, _CONSOLE_HANDLER, _FILE_HANDLER, _CONFIGURED

    if _QUEUE_LISTENER is not None:
        _QUEUE_LISTENER.stop()
        _QUEUE_LISTENER = None

    root_logger = logging.getLogger()
    for handler in (_CONSOLE_HANDLER, _QUEUE_HANDLER):
        if handler is not None:
            root_logger.removeHandler(handler)
            handler.close()
    _CONSOLE_HANDLER = None
    _QUEUE_HANDLER = None

    if _FILE_HANDLER is not None:
        _FILE_HANDLER.close()
        _FILE_HANDLER = None

    _CONFIGURED = False
