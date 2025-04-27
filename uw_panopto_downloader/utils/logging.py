"""Logging utilities for Panopto Downloader."""

import logging

try:
    from rich.console import Console
    from rich.logging import RichHandler

    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


LOG_FILE = "panopto_downloader.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO


_loggers = {}


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        logging.Logger: Configured logger
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)

    if RICH_AVAILABLE:
        rich_handler = RichHandler(rich_tracebacks=True, markup=True)
        logger.addHandler(rich_handler)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(stream_handler)

    _loggers[name] = logger

    return logger
